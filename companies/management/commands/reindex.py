from django.core.management.base import BaseCommand

from elasticsearch.helpers import parallel_bulk
from elasticsearch_dsl.connections import connections
from tqdm import tqdm

from companies.models import Company
from companies.elastic_models import Company as ElasticCompany, companies_idx


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--drop_indices',
            action='store_true',
            dest='drop_indices',
            default=False,
            help='Delete indices before reindex',
        )

    def bulk_write(self, conn, docs_to_index):
        for response in parallel_bulk(
                conn, (d.to_dict(True) for d in docs_to_index)):
            pass

    def handle(self, *args, **options):
        conn = connections.get_connection('default')

        if options["drop_indices"]:
            companies_idx.delete(ignore=404)
            companies_idx.create()
            ElasticCompany.init()

            conn.indices.put_settings(
                index=ElasticCompany._doc_type.index,
                body={
                    'index.max_result_window': 20000000
                }
            )
            qs = Company.objects.all()
        else:
            qs = Company.objects.filter(is_dirty=True)

        docs_to_index = []
        with tqdm() as pbar:
            for p in qs.iterator():
                pbar.update(1)
                docs_to_index.append(ElasticCompany(**p.to_dict()))
                if len(docs_to_index) > 1000:
                    self.bulk_write(conn, docs_to_index)
                    docs_to_index = []

        self.bulk_write(conn, docs_to_index)
        qs.update(is_dirty=False)
