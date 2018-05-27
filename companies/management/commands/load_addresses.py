from tqdm import tqdm
from csv import DictReader
from django.core.management.base import BaseCommand

from elasticsearch.helpers import streaming_bulk
from elasticsearch_dsl.connections import connections

from companies.elastic_models import Address, addresses_idx


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--drop_indices',
            action='store_true',
            dest='drop_indices',
            default=False,
            help='Delete indices before reindex',
        )

        parser.add_argument(
            'in_file',
            help='Input file to index',
        )

    def bulk_write(self, conn, docs_to_index):
        for response in streaming_bulk(
                conn, (d.to_dict(True) for d in docs_to_index)):
            pass

    def handle(self, *args, **options):
        conn = connections.get_connection('default')

        if options["drop_indices"]:
            addresses_idx.delete(ignore=404)
            addresses_idx.create()

        docs_to_index = []
        with open(options["in_file"], "r") as fp:
            r = DictReader(fp)

            with tqdm() as pbar:
                for l in r:
                    pbar.update(1)
                    docs_to_index.append(Address(**l))
                    if len(docs_to_index) > 10000:
                        self.bulk_write(conn, docs_to_index)
                        docs_to_index = []

        self.bulk_write(conn, docs_to_index)
