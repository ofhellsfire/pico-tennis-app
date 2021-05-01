import re

from django.db.models import Q, Sum
from django.shortcuts import render

from .models import (
    Player,
    Match,
    Schedule,
    SummaryTable,
)


TIEBREAK_SCORE_PATTERN = re.compile(f'([(]\d+[)])')


def index(request):
    sum_table = SummaryTable.objects.order_by('-wins', '-sets_diff', '-games_diff')
    matches_count = Match.objects.count()
    latest_results = Match.objects.order_by('-datetime')[:7]
    schedule = Schedule.objects.filter(status__name='S').order_by('datetime')[:7]
    context = {
        'summary': sum_table,
        'results': latest_results,
        'schedule': schedule,
        'matches_count': matches_count,
    }
    return render(request, 'pico/index.html', context)


def schedule(request):
    scheduled = Schedule.objects.filter(status__name='S').order_by('datetime')
    completed = Schedule.objects.filter(status__name='C').order_by('-datetime')
    context = {
        'scheduled': scheduled,
        'completed': completed,
    }
    return render(request, 'pico/schedule.html', context)


def results(request):
    players = Player.objects.all()
    matches = Match.objects.order_by('-datetime')
    _table = []
    for player in players:
        result_table = []
        for other_player in players:
            if player.last_name == other_player.last_name:
                result_table.append(player.last_name)
                break
        for other_player in players:
            if player.last_name != other_player.last_name:
                q1 = Q(player_one__last_name=player.last_name)
                q2 = Q(player_two__last_name=other_player.last_name)
                match = Match.objects.filter(q1 & q2).first()
                if match:
                    result_table.append(match.score)
                else:
                    q1 = Q(player_two__last_name=player.last_name)
                    q2 = Q(player_one__last_name=other_player.last_name)
                    match = Match.objects.filter(q1 & q2).first()
                    if match:
                        result_table.append(reverse_score(match.score))
                    else:
                        result_table.append('')
            else:
                result_table.append('')
        _table.append(result_table)
    context = {
        'players': players,
        'players_results': _table,
        'matches': matches,
    }
    return render(request, 'pico/results.html', context)

# TODO: clean templates, many repeating
# TODO: add JS to show/collapse past results


def reverse_score(score):
    def _reverse(score):
        a, b = score.split(':')
        return f'{b}:{a}'
    split = score.split()
    tiebreaks = []
    for _set in split:
        if '(' in _set:
            tiebreaks.append(_set[3:])
        else:
            tiebreaks.append('')
    tbless_score = TIEBREAK_SCORE_PATTERN.sub('', score).split()
    return ' '.join([f'{_reverse(s)}{t}' for s, t in zip(tbless_score, tiebreaks)])
