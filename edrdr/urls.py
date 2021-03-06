import os
from django.conf.urls import include, url
from django.conf import settings
from django.urls import path
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps import views as sitemaps_views
from django.views.generic import TemplateView
from django.conf.urls.i18n import i18n_patterns
from django.views.decorators.cache import cache_page

from companies.views import (
    CompanyDetail, RevisionDetail, SuggestView, HomeView, SearchView,
    AboutSearchView, AboutAPIView, APIView
)

from companies.sitemaps import sitemaps


urlpatterns = i18n_patterns(
    path('', HomeView.as_view(), name="home"),
    path('about_search', AboutSearchView.as_view(), name="about_search"),
    path('api', AboutAPIView.as_view(), name="about_api"),
    path('search', SearchView.as_view(), name="search>results"),
    path('search/suggest', SuggestView.as_view(), name="search>suggest"),
    path('company/<int:pk>', CompanyDetail.as_view(), name='company>detail'),
    path('revision/<int:pk>', RevisionDetail.as_view(), name='revision>detail'),
) + [
    path('about', TemplateView.as_view(template_name="companies/about.html"),
         name="about"),
    path('secret_api', APIView.as_view(), name="api"),

    path('sitemap.xml',
         cache_page(86400)(sitemaps_views.index),
         {'sitemaps': sitemaps, 'sitemap_url_name': 'sitemaps'}),
    path('sitemap-<section>.xml',
         cache_page(86400)(sitemaps_views.sitemap),
         {'sitemaps': sitemaps}, name='sitemaps'),

    url(r'^admin/', admin.site.urls)
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)