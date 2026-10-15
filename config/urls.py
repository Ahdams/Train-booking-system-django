from django.contrib import admin
from django.urls import path
from core.views import home
from core.route_views import origins, destinations

urlpatterns = [path('routes/origins/', origins, name='origins'), path('routes/destinations/', destinations, name='destinations'), path('admin/', admin.site.urls), path('', home, name='home')]
