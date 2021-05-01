from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('schedule', views.schedule, name='schedule'),
    path('results', views.results, name='results'),
]
