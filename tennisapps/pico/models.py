from operator import sub
import re
import uuid

from dirtyfields import DirtyFieldsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel



TIEBREAK_SCORE_PATTERN = re.compile(f'([(]\d+[)])')


class City(models.Model):
    """Player Home City Model.
    Describes player home town/city.
    """
    class Meta:
        verbose_name_plural = 'cities'

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=32, unique=True)

    def __str__(self):
        return f'City(id={self.id}, name={self.name})'


class Player(TimeStampedModel):
    """Player Model.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=32)
    nickname = models.CharField(max_length=32, default='', blank=True)
    last_name = models.CharField(max_length=32)
    date_birth = models.DateField()
    home_town = models.ForeignKey(City, on_delete=models.CASCADE)

    class Meta:
        """Metadata for Player model."""
        constraints = [
            models.UniqueConstraint(
                name='unique_player',
                fields=['first_name', 'nickname', 'last_name', 'date_birth']
            ),
        ]

    def __str__(self):
        return (f'Player(id={self.id}, first_name={self.first_name}, '
                f'last_name={self.last_name}, date_birth={self.date_birth}, '
                f'home_town={self.home_town}'
        )
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        summary_entry = SummaryTable(player=self, matches=0, wins=0, losses=0, sets_diff=0, games_diff=0)
        summary_entry.save()


class Match(DirtyFieldsMixin, TimeStampedModel):
    """Match Model.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    score = models.CharField(max_length=32, null=True, blank=True)
    datetime = models.DateTimeField()
    duration = models.DurationField(null=True, blank=True)
    court_name = models.CharField(max_length=64, null=True, blank=True)
    player_one = models.ForeignKey(Player, on_delete=models.CASCADE,
                                   related_name='match_player_one')
    player_two = models.ForeignKey(Player, on_delete=models.CASCADE,
                                   related_name='match_player_two')
    winner = models.ForeignKey(Player, on_delete=models.CASCADE, null=True, blank=True,
                               related_name='match_winner', editable=False)
    loser = models.ForeignKey(Player, on_delete=models.CASCADE, null=True, blank=True,
                              related_name='match_loser', editable=False)

    class Meta:
        """Metadata for Single Match model."""
        constraints = [
            models.UniqueConstraint(fields=['player_one', 'player_two'],
                                    name='unique_match'),
            models.CheckConstraint(
                name='distinct_players_in_match',
                check=~models.Q(player_one=models.F('player_two'))
            ),
            models.CheckConstraint(
                name='distinct_winner_loser_in_match',
                check=~models.Q(winner=models.F('loser'))
            ),
            models.CheckConstraint(
                name='only_participants_can_be_winner_loser_in_match',
                check=(
                    models.Q(winner=models.F('player_one'), loser=models.F('player_two')) |
                    models.Q(winner=models.F('player_two'), loser=models.F('player_one'))
                )
            ),
            models.CheckConstraint(
                name='match_xnor_winner_loser',
                check=(
                    models.Q(winner__isnull=True, loser__isnull=True, score__isnull=True) |
                    models.Q(winner__isnull=False, loser__isnull=False, score__isnull=False)
                ),
            ),
        ]
        verbose_name_plural = 'matches'

    def __str__(self):
        return (f'Match(id={self.id}, score={self.score}, '
                f'datetime={self.datetime}, duration={self.duration}, '
                f'court_name={self.court_name}, '
                f'player_one={self.player_one}, player_two={self.player_two}, '
                f'winner={self.winner}, loser={self.loser})')

    def clean(self):
        one_to_two = Match.objects.filter(player_one=self.player_one, player_two=self.player_two)
        two_to_one = Match.objects.filter(player_one=self.player_two, player_two=self.player_one)

        if one_to_two.exists() or two_to_one.exists():
            raise ValidationError(_('Match already exists'), code='already_exists')

    def save(self, *args, **kwargs):
        if Match.objects.filter(pk=self.pk).exists() and self.is_dirty(check_relationship=True):
            dirty_fields = self.get_dirty_fields(check_relationship=True)
            old_tss = TennisScoreStats(
                unit_one=dirty_fields.get('player_one', self.player_one),
                unit_two=dirty_fields.get('player_two', self.player_two),
                score=dirty_fields.get('score', self.score)
            )
            old_tss.calculate()
            self._inverse_summary_table(old_tss)
        tss = TennisScoreStats(unit_one=self.player_one, unit_two=self.player_two,
                               score=self.score)
        tss.calculate()
        self.winner = tss.winner
        self.loser = tss.loser
        super().save(*args, **kwargs)
        self._update_summary_table(tss)

    def _update_summary_table(self, tss):
        p_one_summary = SummaryTable.objects.get(player=self.player_one.pk)
        p_two_summary = SummaryTable.objects.get(player=self.player_two.pk)
        p_one_summary.matches += 1
        p_two_summary.matches += 1
        if tss.winner.pk == self.player_one.pk:
            p_one_summary.wins += 1
            p_two_summary.losses += 1
            p_one_summary.sets_diff += tss.sets_diff
            p_two_summary.sets_diff -= tss.sets_diff
        else:
            p_two_summary.wins += 1
            p_one_summary.losses += 1
            p_two_summary.sets_diff += tss.sets_diff
            p_one_summary.sets_diff -= tss.sets_diff
        p_one_summary.games_diff += tss.unit_one_games_diff
        p_two_summary.games_diff += tss.unit_two_games_diff
        p_one_summary.save()
        p_two_summary.save()

    def _inverse_summary_table(self, tss):
        p_one_summary = SummaryTable.objects.get(player=tss.unit_one)
        p_two_summary = SummaryTable.objects.get(player=tss.unit_two)
        p_one_summary.matches -= 1
        p_two_summary.matches -= 1
        if tss.winner == tss.unit_one:
            p_one_summary.wins -= 1
            p_two_summary.losses -= 1
            p_one_summary.sets_diff -= tss.sets_diff
            p_two_summary.sets_diff += tss.sets_diff
        else:
            p_two_summary.wins -= 1
            p_one_summary.losses -= 1
            p_two_summary.sets_diff -= tss.sets_diff
            p_one_summary.sets_diff += tss.sets_diff
        p_one_summary.games_diff -= tss.unit_one_games_diff
        p_two_summary.games_diff -= tss.unit_two_games_diff
        p_one_summary.save()
        p_two_summary.save()


class ScheduleMatchStatus(models.Model):

    class Status(models.TextChoices):
        """Aux class for Status Choices."""
        SCHEDULED = 'S', _('Scheduled')
        COMPLETE = 'C', _('Complete')

    class Meta:
        """Metadata for ScheduleMatchStatus model."""
        constraints = [
            models.CheckConstraint(
                name='only_known_values_are_allowed_for_schedule_match_status',
                check=(models.Q(name='S') |
                       models.Q(name='C'))
            ),
        ]
        verbose_name_plural = 'schedule match status'

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=1, choices=Status.choices, unique=True,
                            default=Status.SCHEDULED)

    def __str__(self):
        return f'ScheduleMatchStatus(id={self.id}, name={self.name})'

    def is_upperclass(self):
        """Aux method for enumeration presence test."""
        return self.name in {
            self.Status.SCHEDULED,
            self.Status.COMPLETE,
        }

    
class Schedule(models.Model):
    id = models.AutoField(primary_key=True)
    player_one = models.ForeignKey(Player, on_delete=models.CASCADE,
                                   related_name='schedule_player_one')
    player_two = models.ForeignKey(Player, on_delete=models.CASCADE,
                                   related_name='schedule_player_two')
    datetime = models.DateTimeField()
    court_name = models.CharField(max_length=32, null=True, blank=True)
    status = models.ForeignKey(ScheduleMatchStatus, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['player_one', 'player_two'],
                                    name='unique_schedule_match'),
        ]

    def __str__(self):
        return (f'Schedule(id={self.id}, player_one={self.player_one}, '
                f'player_two={self.player_two}, datetime={self.datetime}, '
                f'court_name={self.court_name}, status={self.status})')

    def clean(self):
        one_to_two = Schedule.objects.filter(player_one=self.player_one, player_two=self.player_two)
        two_to_one = Schedule.objects.filter(player_one=self.player_two, player_two=self.player_one)

        if one_to_two.exists() or two_to_one.exists():
            raise ValidationError(_('Match already scheduled'), code='already_scheduled')


class SummaryTable(models.Model):
    id = models.AutoField(primary_key=True)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='summary_player')  # TODO: need to be constrained to unique player & tournament
    matches = models.PositiveSmallIntegerField()
    wins = models.PositiveSmallIntegerField()
    losses = models.PositiveSmallIntegerField()
    sets_diff = models.SmallIntegerField()
    games_diff = models.SmallIntegerField()


class TennisScoreStats:

    def __init__(self, unit_one, unit_two, score):
        self.score = score
        self.unit_one = unit_one
        self.unit_two = unit_two
        self.winner = None
        self.loser = None
        self.sets_diff = None
        self.unit_one_games_diff = None
        self.unit_two_games_diff = None

        self._score = None

        self.score_format = None
        self.match_rules = None

    def __repr__(self):
        return (f'TennisScoreStats(score="{self.score}", unit_one={self.unit_one}, '
                f'unit_two={self.unit_two}, winner={self.winner}, loser={self.loser}, '
                f'sets_diff={self.sets_diff}, unit_one_games_diff={self.unit_one_games_diff}, '
                f'unit_two_games_diff={self.unit_two_games_diff})')

    def calculate(self):
        self._split_score()
        self._set_winner_loser()
        self._set_sets_diff()
        self._set_games_diff()

    def _split_score(self):
        score = TIEBREAK_SCORE_PATTERN.sub('', self.score)  # elimiate tiebreak scores
        self._score = [
            [int(x) for x in sets.split(':')]  # TODO: change to formatter
            for sets in score.split()
        ]
    
    def _set_winner_loser(self):
        set_winners = list(map(lambda x: x[0] < x[1], self._score))
        if set_winners.count(False) > set_winners.count(True):
            self.winner, self.loser = self.unit_one, self.unit_two
        else:
            self.winner, self.loser = self.unit_two, self.unit_one

    def _set_sets_diff(self):
        if len(self._score) == 2:
            self.sets_diff = 2
        else:
            self.sets_diff = 1

    def _set_games_diff(self):
        diff = 0
        if len(self._score) == 3:
            if self._score[2][0] > self._score[2][1]:
                diff = 1
            else:
                diff = -1
        self.unit_one_games_diff = diff + sub(*[sum(x) for x in zip(*self._score[:2])])
        self.unit_two_games_diff = self.unit_one_games_diff * (-1)


# TODO: hide django admin page
# TODO: connect schedule and match models: when match gets created, schedule is created as well. When match score is set, schedule must be Completed
