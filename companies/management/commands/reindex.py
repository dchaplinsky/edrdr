from django.core.management.base import BaseCommand

from elasticsearch.helpers import parallel_bulk
from elasticsearch_dsl.connections import connections
from tqdm import tqdm

from companies.models import Company, CompanySnapshotFlags
from companies.elastic_models import Company as ElasticCompany, companies_idx


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--drop_indices",
            action="store_true",
            dest="drop_indices",
            default=False,
            help="Delete indices before reindex",
        )

        parser.add_argument(
            "--force",
            action="store_true",
            dest="force",
            default=False,
            help="Forcely reindex everything",
        )

    def bulk_write(self, conn, docs_to_index):
        for response in parallel_bulk(conn, (d.to_dict(True) for d in docs_to_index)):
            pass

    def handle(self, *args, **options):
        conn = connections.get_connection("default")

        qs = Company.objects.all()
        if options["drop_indices"]:
            companies_idx.delete(ignore=404)
            companies_idx.create()
            ElasticCompany.init()

            conn.indices.put_settings(
                index=ElasticCompany._doc_type.index,
                body={"index.max_result_window": 20000000},
            )
        else:
            if not options["force"]:
                qs = Company.objects.filter(is_dirty=True)

        docs_to_index = []

        for p in tqdm(qs.nocache().iterator()):
            docs_to_index.append(ElasticCompany(**p.to_dict()))
            if len(docs_to_index) > 2000:
                self.bulk_write(conn, docs_to_index)
                docs_to_index = []

        self.bulk_write(conn, docs_to_index)
        qs.update(is_dirty=False)
