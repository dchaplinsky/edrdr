from qartez.sitemaps import RelAlternateHreflangSitemap
from companies.models import Company
from django.conf import settings
from django.utils.translation import activate


class CompanySitemap(RelAlternateHreflangSitemap):
    changefreq = "monthly"
    limit = 5000

    def items(self):
        return Company.objects.filter().nocache().order_by("pk")

    def lastmod(self, obj):
        return obj.last_modified

    def alternate_hreflangs(self, obj):
        res = []

        for lang, _ in settings.LANGUAGES:
            activate(lang)
            res.append(
                (lang, "%s".format(self.location(obj)))
            )

        return res


sitemaps = {
    "companies": CompanySitemap
}
