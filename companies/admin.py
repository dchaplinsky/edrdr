from django.contrib import admin
from companies.models import Revision


class RevisionAdmin(admin.ModelAdmin):
    pass


admin.site.register(Revision, RevisionAdmin)
