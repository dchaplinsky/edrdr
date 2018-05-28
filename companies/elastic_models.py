from django.conf import settings

from Levenshtein import distance
from elasticsearch_dsl import (
    DocType, Keyword, Text, Index, analyzer, tokenizer, token_filter,
    MultiSearch, MetaField, Object)
from elasticsearch_dsl.query import Q

ADDRESSES_INDEX = 'addresses'
COMPANIES_INDEX = 'edrdr_companies'


class Address(DocType):
    """Address document."""

    parentCode = Keyword(index=True)
    regionCode = Keyword(index=True)
    ATOCode = Keyword(index=True)
    level = Keyword(index=True)
    code = Keyword(index=True)
    streetCode = Keyword(index=True)
    postalCode = Keyword(index=True, copy_to="all")
    precinctNum = Keyword(index=True)
    districtNum = Keyword(index=True)
    region = Keyword(index=True, copy_to="all")
    district = Keyword(index=True, copy_to="all")
    locality = Keyword(index=True, copy_to="all")
    street = Keyword(index=True, copy_to="all")
    oldStreet = Keyword(index=True, copy_to="all")
    oldDistrict = Keyword(index=True, copy_to="all")
    oldLocality = Keyword(index=True, copy_to="all")

    @classmethod
    def validate(cls, address):
        try:
            if "fullAddress" not in address:
                address["fullAddress"] = ''

            if "source" not in address:
                address["source"] = ''

            ms = MultiSearch(index=ADDRESSES_INDEX)

            should = []
            if "postalCode" in address:
                should.append(Q('match', postalCode=address["postalCode"]))
            if "region" in address:
                should.append(Q('match', region=address["region"]))

            if "fullAddress" in address:
                ms = ms.add(
                    cls.search().query(
                        "bool",
                        must=Q(
                            'simple_query_string',
                            fields=['all.shingle'],
                            query=address["fullAddress"],
                            default_operator='or'
                        ),
                        should=should
                    )
                ).add(
                    cls.search().query(
                        "bool",
                        must=Q(
                            'simple_query_string',
                            fields=['all'],
                            query=address["fullAddress"],
                            default_operator='or'
                        ),
                        should=should
                    )
                )

            if address["source"]:
                ms = ms.add(
                    cls.search().query(
                        "bool",
                        must=Q(
                            'simple_query_string',
                            fields=['all'],
                            query=address["source"],
                            default_operator='or'
                        ),
                        should=should
                    )
                )

            responses = ms.execute()

            new_address = {}
            max_score = 0
            for resp in responses:
                if resp.hits.max_score is not None and resp.hits.max_score >= max_score:
                    new_address = resp[0].to_dict()
                    max_score = resp.hits.max_score

            if new_address:
                address["fullAddress"] = ''

                if new_address.get("postalCode"):
                    address["postalCode"] = new_address["postalCode"].rjust(5, "0")
                    address["fullAddress"] += address["postalCode"]

                if new_address.get("region"):
                    address["region"] = new_address["region"]

                if new_address.get("region") not in ['місто Київ', 'місто Севастополь']:
                    address["fullAddress"] += ', ' + address["region"]

                if new_address.get("district"):
                    address["district"] = new_address["district"]
                    address["fullAddress"] += ', ' + address["district"]

                if address.get("locality") and new_address.get("locality"):
                    if (distance(new_address["locality"].lower(), address["locality"].lower()) < 6 or
                            distance(new_address["oldLocality"].lower(), address["locality"].lower()) < 6):
                        address["locality"] = new_address["locality"]

                    address["fullAddress"] += ', ' + address["locality"]
                elif new_address.get("locality"):
                    address["locality"] = new_address["locality"]
                    address["fullAddress"] += ', ' + address["locality"]

                if address.get("streetAddress") and new_address.get("street"):
                    if (distance(new_address["street"].lower(), address["streetAddress"].lower()) < 6 or
                            distance(new_address["oldStreet"].lower(), address["streetAddress"].lower()) < 6):
                        address["streetAddress"] = new_address["street"]

                    address["fullAddress"] += ', ' + address["streetAddress"]

                if new_address.get("oldStreet"):
                    address["oldStreet"] = new_address["oldStreet"]

                if new_address.get("oldDistrict"):
                    address["oldDistrict"] = new_address["oldDistrict"]

                if new_address.get("oldLocality"):
                    address["oldLocality"] = new_address["oldLocality"]

                if address.get("streetNumber"):
                    address["streetAddress"] += ', ' + address["streetNumber"]
                    address["fullAddress"] += ', ' + address["streetNumber"]

                    del address["streetNumber"]
        except (ValueError, KeyError, IndexError) as e:
            print(e)
            return address

        return address

    class Meta:
        index = ADDRESSES_INDEX
        all = MetaField(
            type=Text(
                analyzer='ukrainian',
                fields={
                    "shingle": Text(analyzer="shingleAnalyzer", search_analyzer="shingleAnalyzer",)
                }
            )
        )


addresses_idx = Index(ADDRESSES_INDEX)

addresses_idx.settings(
    number_of_shards=settings.NUM_THREADS
)

addresses_idx.doc_type(Address)

shingle_analyzer = analyzer(
    'shingleAnalyzer',
    tokenizer=tokenizer(
        'ukrainianTokenizer',
        type='pattern',
        pattern='[А-ЯЄІЇҐа-яєіїґA-Za-z0-9\']+'
    ),
    filter=[
        token_filter(
            'shingleFilter',
            type='shingle',
            max_shingle_size=5,
            min_shingle_size=2,
            output_unigrams=True
        ),
        'lowercase'
    ],
)

addresses_idx.analyzer(shingle_analyzer)

companies_idx = Index(COMPANIES_INDEX)
companies_idx.settings(
    number_of_shards=settings.NUM_THREADS
)

namesAutocompleteAnalyzer = analyzer(
    'namesAutocompleteAnalyzer',
    tokenizer=tokenizer(
        'autocompleteTokenizer',
        type='edge_ngram',
        min_gram=2,
        max_gram=20,
        token_chars=[
            'letter',
            'digit'
        ]
    ),
    filter=[
        "lowercase"
    ]
)
namesAutocompleteSearchAnalyzer = analyzer(
    'namesAutocompleteSearchAnalyzer',
    tokenizer=tokenizer("lowercase")
)

companies_idx.analyzer(namesAutocompleteAnalyzer)
companies_idx.analyzer(namesAutocompleteSearchAnalyzer)


@companies_idx.doc_type
class Company(DocType):
    """Company document."""

    full_edrpou = Keyword(index=True, copy_to="all")
    addresses = Text(analyzer='ukrainian')
    persons = Text(analyzer='ukrainian')
    companies = Text(analyzer='ukrainian')
    company_profiles = Keyword(index=True, copy_to="all")
    latest_record = Object()
    raw_records = Text(analyzer='ukrainian')
    names_autocomplete = Text(
        analyzer='namesAutocompleteAnalyzer',
        search_analyzer="namesAutocompleteSearchAnalyzer"
    )

    class Meta:
        pass
