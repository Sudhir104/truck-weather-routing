from django.urls import path
from routing.views import plan

urlpatterns = [path("api/plan/", plan)]
