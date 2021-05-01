from django.contrib import admin

from .models import (
    City,
    Player,
    Match,
    Schedule,
    ScheduleMatchStatus,
    SummaryTable,
    TennisScoreStats,
)


class MatchAdmin(admin.ModelAdmin):
    model = Match
    actions = ['delete_model']

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            p_one_summary = SummaryTable.objects.get(player=obj.player_one.pk)
            p_two_summary = SummaryTable.objects.get(player=obj.player_two.pk)
            tss = TennisScoreStats(unit_one=obj.player_one, unit_two=obj.player_two,
                                   score=obj.score)
            tss.calculate()
            p_one_summary.matches -= 1
            p_two_summary.matches -= 1
            if obj.winner.pk == obj.player_one.pk:
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
            obj.delete()
            p_one_summary.save()
            p_two_summary.save()

    def delete_model(self, request, obj):
        _obj = obj.first()
        p_one_summary = SummaryTable.objects.get(player=_obj.player_one.pk)
        p_two_summary = SummaryTable.objects.get(player=_obj.player_two.pk)
        tss = TennisScoreStats(unit_one=_obj.player_one, unit_two=_obj.player_two,
                               score=_obj.score)
        tss.calculate()
        p_one_summary.matches -= 1
        p_two_summary.matches -= 1
        if _obj.winner.pk == _obj.player_one.pk:
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

        obj.delete()

        p_one_summary.save()
        p_two_summary.save()

    # TODO: DRY violations

admin.site.register((City, Player, Schedule, ScheduleMatchStatus))
admin.site.register(Match, MatchAdmin)
