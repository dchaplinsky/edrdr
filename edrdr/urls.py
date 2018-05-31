from django.conf.urls import include, url
from django.conf import settings
from django.urls import path
from django.contrib import admin
from django.views.generic import TemplateView
from django.conf.urls.i18n import i18n_patterns

from companies.views import CompanyDetail, RevisionDetail, SuggestView


urlpatterns = i18n_patterns(
    path('', TemplateView.as_view(template_name="companies/home.html"),
         name="home"),
    path('search/suggest', SuggestView.as_view(), name="search>suggest"),
    path('company/<int:pk>', CompanyDetail.as_view(), name='company>detail'),
    path('revision/<int:pk>', RevisionDetail.as_view(), name='revision>detail'),
) + [url(r'^admin/', admin.site.urls)]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
