import re

from django.views import View
from django.views.generic import DetailView, TemplateView
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from elasticsearch_dsl.query import Q
from elasticsearch_dsl import MultiSearch

from companies.models import Company, Revision, Person
from companies.elastic_models import Company as ElasticCompany
from companies.tools.paginator import paginated


class RevisionDetail(DetailView):
    context_object_name = "revision"
    queryset = Revision.objects.filter(ignore=False)


class CompanyDetail(DetailView):
    context_object_name = "company"
    queryset = Company.objects.prefetch_related("records", "persons")


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(kwargs["object"].get_grouped_record())

        return context


class APIView(View):
    def get(self, request):
        edrpous = map(lambda x: x.lstrip("0"), request.GET.getlist("edrpou", []))

        queryset = Company.objects.prefetch_related("records", "persons").filter(
            pk__in=list(edrpous)
        )

        return JsonResponse(
            {
                c.pk: {
                    k: v
                    for k, v in c.to_dict().items()
                    if k in ["raw_persons", "latest_record"]
                }
                for c in queryset.iterator()
            },
            safe=False,
        )


class SuggestView(View):
    def get(self, request):
        q = request.GET.get("q", "").strip()

        suggestions = []
        seen = set()

        s = (
            ElasticCompany.search()
            .source(["names_autocomplete"])
            .highlight("names_autocomplete")
            .highlight_options(
                order="score",
                fragment_size=100,
                number_of_fragments=10,
                type="fvh",
                pre_tags=["<strong>"],
                post_tags=["</strong>"],
            )
        )

        s = s.query(
            "bool",
            must=[Q("match", names_autocomplete={"query": q, "operator": "and"})],
            should=[
                Q("match_phrase", names_autocomplete={"query": q, "boost": 2}),
                Q(
                    "span_first",
                    match=Q("span_term", names_autocomplete=q),
                    end=4,
                    boost=2,
                ),
            ],
        )[:150]

        res = s.execute()

        for r in res:
            if "names_autocomplete" in r.meta.highlight:
                for candidate in r.meta.highlight["names_autocomplete"]:
                    if candidate.lower() not in seen:
                        suggestions.append(candidate)
                        seen.add(candidate.lower())

        ms = MultiSearch()

        number_of_suggs = 20
        for sugg in suggestions[:number_of_suggs]:
            ms = ms.add(
                ElasticCompany.search()
                .query(
                    "match_phrase",
                    all={
                        "query": sugg.replace("<strong>", "").replace("</strong>", "")
                    },
                )
                .source(["latest_record", "full_edrpou", "companies"])[:1]
            )

        rendered_result = []
        if suggestions:
            rendered_result = [
                render_to_string(
                    "companies/autocomplete.html",
                    {"result": {"hl": k, "company": company}},
                )
                for k, company in zip(suggestions[:number_of_suggs], ms.execute())
            ]

        return JsonResponse(rendered_result, safe=False)


class HomeView(TemplateView):
    template_name = "companies/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update(
            {
                "num_of_companies": Company.objects.count(),
                "num_of_persons": Person.objects.count(),
                "num_of_beneficiaries": Person.objects.filter(
                    person_type="owner"
                ).count(),
            }
        )

        return context


class AboutSearchView(TemplateView):
    template_name = "companies/about_search.html"


class AboutAPIView(TemplateView):
    template_name = "companies/about_api.html"


class SearchView(TemplateView):
    template_name = "companies/search.html"

    def get(self, request, *args, **kwargs):
        context = super().get_context_data(**kwargs)

        query = request.GET.get("q", "")
        search_type = request.GET.get("search_type", "strict")
        is_addr = request.GET.get("is_addr", "false") == "true"
        if search_type not in ["strict", "loose"]:
            search_type = "strict"

        if query:
            nwords = len(re.findall(r"\w{2,}", query))

            if nwords > 3:
                should_match = str(nwords - int(nwords > 6) - 1)
            else:
                should_match = "100%"

            if not is_addr:
                strict_query = ElasticCompany.search().query(
                    "match_phrase", all={"query": query, "slop": 6}
                )
            else:
                no_zip_q = re.sub(r"\b\d{5,}\W", "", query)
                strict_query = ElasticCompany.search().query(
                    "match", addresses={"query": no_zip_q, "operator": "and"}
                )

            loose_query = ElasticCompany.search().query(
                "match",
                all={
                    "query": query,
                    "operator": "or",
                    "minimum_should_match": should_match,
                },
            )

            ms = MultiSearch()
            ms = ms.add(strict_query[:0])
            ms = ms.add(loose_query[:0])
            sc, lc = ms.execute()

            strict_count = sc.hits.total
            loose_count = lc.hits.total

            if search_type == "loose":
                base_qs = loose_query
                base_count = loose_count
            else:
                base_qs = strict_query
                base_count = strict_count

            qs = base_qs
        else:
            qs = ElasticCompany.search().query("match_all")

            base_count = loose_count = strict_count = qs.count()

        results = (
            qs.highlight_options(
                order="score", pre_tags=['<u class="match">'], post_tags=["</u>"]
            )
            .highlight(
                "*",
                require_field_match=False,
                fragment_size=100,
                number_of_fragments=10,
                type="fvh"
            )
            .source(
                [
                    "full_edrpou",
                    "latest_record.short_name",
                    "latest_record.name",
                    "latest_record.status",
                    "latest_record.location",
                ]
            )
        )

        search_results = paginated(request, results)
        for res in search_results:
            res.hl = []
            seen_hl = set()
            for h_field in getattr(res.meta, "highlight", {}):
                for content in res.meta.highlight[h_field]:
                    res.hl.append(content)

        context.update(
            {
                "search_results": search_results,
                "query": query,
                "search_type": search_type,
                "strict_count": strict_count,
                "loose_count": loose_count,
                "base_count": base_count,
            }
        )

        return self.render_to_response(context)
