from django.views.generic import DetailView
from companies.models import Company, Revision
from collections import OrderedDict, defaultdict


class RevisionDetail(DetailView):
    context_object_name = 'revision'
    queryset = Revision.objects.all()


class CompanyDetail(DetailView):
    context_object_name = 'company'
    queryset = Company.objects.prefetch_related("records", "persons")

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
                else:
                    pass
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = kwargs["object"]

        used_revisions = set()
        latest_record = None
        latest_record_revision = 0
        records_revisions = defaultdict(dict)

        latest_persons = []
        latest_persons_revision = 0
        global_revisions = OrderedDict([
            (r.pk, r)
            for r in Revision.objects.filter(imported=True).order_by("pk")
        ])

        for rec in obj.records.all():
            for r in rec.revisions:
                records_revisions[r] = rec

            max_revision = max(rec.revisions)
            if max_revision > latest_record_revision:
                latest_record = rec
                latest_record_revision = max_revision
            used_revisions |= set(rec.revisions)

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

        def hash_for_groups(records):
            return tuple(sorted(r.person_hash for r in records))

        context.update({
            "global_revisions": global_revisions,
            "used_revisions": sorted(used_revisions),
            "latest_record": latest_record,
            "latest_record_revision": latest_record_revision,
            "grouped_company_records": self.group_revisions(
                global_revisions,
                records_revisions,
                hash_field_getter=lambda rec: getattr(rec, "company_hash")
            ),
            "grouped_persons_records": self.group_revisions(
                global_revisions,
                persons_revisions,
                hash_field_getter=hash_for_groups
            ),
            "latest_persons": latest_persons,
            "latest_persons_revision": latest_persons_revision,
            "records_revisions": records_revisions
        })

        return context
