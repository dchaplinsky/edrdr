from elasticsearch_dsl import DocType, Integer, Keyword, Text, Index, analyzer, tokenizer, token_filter

ADDRESSES_INDEX = 'addresses'


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
    all = Text(analyzer='ukrainian', fields={
        "shingle": Text(analyzer="shingleAnalyzer", search_analyzer="shingleAnalyzer",)
    })

    class Meta:
        index = ADDRESSES_INDEX


addresses_idx = Index(ADDRESSES_INDEX)

addresses_idx.settings(
    number_of_shards=1
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
