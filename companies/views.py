import re
from collections import OrderedDict, defaultdict

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
    context_object_name = 'revision'
    queryset = Revision.objects.filter(ignore=False)


class CompanyDetail(DetailView):
    context_object_name = 'company'
    queryset = Company.objects.prefetch_related("records", "persons")

    status_order = (
        "зареєстровано",
        "зареєстровано, свідоцтво про державну реєстрацію недійсне",
        "порушено справу про банкрутство",
        "порушено справу про банкрутство (санація)",
        "в стані припинення",
        "припинено",
    )

    def group_revisions(self, revisions, records, hash_field_getter):
        periods = []
        current_record = None

        current_hash = None
        start_revision = None
        finish_revision = None

        def add_group(current_record):
            if current_record is not None:
                periods.append({
                    "start_revision": start_revision,
                    "finish_revision": finish_revision,
                    "record": current_record,
                })
            current_record = None

        for r, revision in revisions.items():
            rec = records.get(r)
            if rec is None:
                if current_hash is not None:
                    # Record disappeared from a history at some point
                    add_group(current_record)
                    current_hash = None
                    start_revision = revision
                    finish_revision = revision
                else:
                    start_revision = revision
                    finish_revision = revision
                    # Record for that company wasn't
                    # present at the time of given revision
                continue

            if current_hash == hash_field_getter(rec):
                # If nothing changed between two consequent revisions
                # adding current record to the group
                finish_revision = revision
            else:
                add_group(current_record)
                current_record = rec
                current_hash = hash_field_getter(rec)
                start_revision = revision
                finish_revision = revision

        add_group(current_record)

        return periods

    def find_newest_record(self, a, b):
        """
        Weird heuristic to identify the latest record in the dump
        """
        def get_pos(obj):
            try:
                return self.status_order.index(obj.get_status_display().lower())
            except ValueError:
                return 10

        a_pos = get_pos(a)
        b_pos = get_pos(b)

        if a_pos > b_pos:
            return a
        elif b_pos > a_pos:
            return b
        else:
            return a

    def key_by_company_status(self, obj):
        try:
            return self.status_order.index(obj.get_status_display().lower())
        except ValueError:
            return -len(self.status_order)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = kwargs["object"]

        used_revisions = set()
        latest_record = None
        latest_record_revision = 0
        records_revisions = defaultdict(list)

        latest_persons = []
        latest_persons_revision = 0
        global_revisions = OrderedDict([
            (r.pk, r)
            for r in Revision.objects.filter(imported=True, ignore=False).order_by("pk")
        ])

        for rec in obj.records.all():
            for r in rec.revisions:
                if r in records_revisions:
                    records_revisions[r].append(rec)
                else:
                    records_revisions[r] = [rec]

            max_revision = max(rec.revisions)
            if max_revision > latest_record_revision:
                latest_record = rec
                latest_record_revision = max_revision
            used_revisions |= set(rec.revisions)

        # Now let's sort company records inside each revision
        for r, records in records_revisions.items():
            records_revisions[r] = sorted(records, key=self.key_by_company_status, reverse=True)

        persons_revisions = defaultdict(list)
        for p in obj.persons.all():
            max_revision = max(p.revisions)
            for r in p.revisions:
                persons_revisions[r].append(p)

            if max_revision > latest_persons_revision:
                latest_persons = [p]
                latest_persons_revision = max_revision
            elif max_revision == latest_persons_revision:
                latest_persons.append(p)

            used_revisions |= set(p.revisions)

        def hash_for_persons(records):
            return tuple(sorted(r.person_hash for r in records))

        def hash_for_companies(records):
            return tuple(sorted(r.company_hash for r in records))

        context.update({
            "global_revisions": global_revisions,
            "used_revisions": sorted(used_revisions),
            "latest_record": latest_record,
            "latest_record_revision": latest_record_revision,
            "grouped_company_records": self.group_revisions(
                global_revisions,
                records_revisions,
                hash_field_getter=hash_for_companies
            ),
            "grouped_persons_records": self.group_revisions(
                global_revisions,
                persons_revisions,
                hash_field_getter=hash_for_persons
            ),
            "latest_persons": latest_persons,
            "latest_persons_revision": latest_persons_revision,
            "records_revisions": records_revisions
        })

        return context


class SuggestView(View):
    def get(self, request):
        q = request.GET.get('q', '').strip()

        suggestions = []
        seen = set()

        s = ElasticCompany.search().source(
            ['names_autocomplete']
        ).highlight('names_autocomplete').highlight_options(
            order='score', fragment_size=100,
            number_of_fragments=10,
            pre_tags=['<strong>'],
            post_tags=["</strong>"]
        )

        s = s.query(
            "bool",
            must=[
                Q(
                    "match",
                    names_autocomplete={
                        "query": q,
                        "operator": "and"
                    }
                )
            ],
            should=[
                Q(
                    "match_phrase",
                    names_autocomplete={
                        "query": q,
                        "boost": 2
                    },
                ),
                Q(
                    "span_first",
                    match=Q(
                        "span_term",
                        names_autocomplete=q
                    ),
                    end=4,
                    boost=2
                )
            ]
        )[:200]

        res = s.execute()

        for r in res:
            if "names_autocomplete" in r.meta.highlight:
                for candidate in r.meta.highlight["names_autocomplete"]:
                    if candidate.lower() not in seen:
                        suggestions.append(candidate)
                        seen.add(candidate.lower())

        ms = MultiSearch()

        for sugg in suggestions[:20]:
            q = strip_tags(sugg)
            ms = ms.add(ElasticCompany.search().query(
                "match_phrase",
                all={
                    "query": q
                }
            ).source(["latest_record", "full_edrpou", "companies", "latest_record"])[:1])


        rendered_result = [
            render_to_string("companies/autocomplete.html", {
                "result": {
                    "hl": k,
                    "company": company
                }
            })
            for k, company in zip(suggestions[:20], ms.execute())
        ]

        return JsonResponse(rendered_result, safe=False)


class HomeView(TemplateView):
    template_name = "companies/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update({
            "num_of_companies": Company.objects.count(),
            "num_of_persons": Person.objects.count(),
            "num_of_beneficiaries": Person.objects.filter(person_type="owner").count()
        })

        return context


class SearchView(TemplateView):
    template_name = "companies/search.html"

    def get(self, request, *args, **kwargs):
        context = super().get_context_data(**kwargs)

        query = request.GET.get("q", "")
        search_type = request.GET.get("search_type", "strict")
        is_addr = request.GET.get("is_addr", "false") == "true"
        if search_type not in ["strict", "loose", "fuzzy"]:
            search_type = "strict"

        if query:
            nwords = len(re.findall(r'\w{2,}', query))

            if nwords > 3:
                should_match = str(nwords - int(nwords > 6) - 1)
            else:
                should_match = "100%"

            if not is_addr:
                strict_query = ElasticCompany.search().query(
                    "match_phrase",
                    all={
                        "query": query
                    }
                )

                fuzzy_query = ElasticCompany.search().query(
                    "match",
                    all={
                        "query": query,
                        "operator": "and",
                        "fuzziness": "auto"
                    }
                )
            else:
                no_zip_q = re.sub(r"\b\d{5,}\W", "", query)
                strict_query = ElasticCompany.search().query(
                    "match",
                    addresses={
                        "query": no_zip_q,
                        "operator": "and",
                    }
                )

                fuzzy_query = ElasticCompany.search().query(
                    "match",
                    addresses={
                        "query": no_zip_q,
                        "operator": "or",
                        "minimum_should_match": "-10%",
                        "fuzziness": "auto"
                    }
                )

            loose_query = ElasticCompany.search().query(
                "match",
                all={
                    "query": query,
                    "operator": "or",
                    "minimum_should_match": should_match,
                }
            )

            ms = MultiSearch()
            ms = ms.add(strict_query[:0])
            ms = ms.add(loose_query[:0])
            ms = ms.add(fuzzy_query[:0])
            sc, lc, fc = ms.execute()

            strict_count = sc.hits.total
            loose_count = lc.hits.total
            fuzzy_count = fc.hits.total

            if search_type == "fuzzy":
                base_qs = fuzzy_query
                base_count = fuzzy_count
            elif search_type == "loose":
                base_qs = loose_query
                base_count = loose_count
            else:
                base_qs = strict_query
                base_count = strict_count

            qs = base_qs
        else:
            qs = ElasticCompany.search().query('match_all')

            base_count = fuzzy_count = loose_count = strict_count = qs.count()

        results = qs.highlight_options(
            order='score',
            pre_tags=['<u class="match">'],
            post_tags=["</u>"]
        ).highlight(
            "*",
            require_field_match=False,
            fragment_size=100,
            number_of_fragments=10
        ).source([
            "full_edrpou",
            "latest_record.short_name",
            "latest_record.name",
            "latest_record.status",
            "latest_record.location"
        ])

        search_results = paginated(request, results)
        for res in search_results:
            res.hl = []
            seen_hl = set()
            for h_field in getattr(res.meta, "highlight", {}):
                for content in res.meta.highlight[h_field]:
                    res.hl.append(content)

        context.update({
            "search_results": search_results,
            "query": query,
            "search_type": search_type,
            "strict_count": strict_count,
            "loose_count": loose_count,
            "fuzzy_count": fuzzy_count,
            "base_count": base_count,
        })

        return self.render_to_response(context)
