import unittest
from copy import deepcopy
from pprint import pprint

from wikibaseintegrator import datatypes, WikibaseIntegrator
from wikibaseintegrator.datatypes import String, Math, ExternalID, Time, URL, MonolingualText, Quantity, CommonsMedia, GlobeCoordinate, GeoShape, Property, TabularData, \
    MusicalNotation, Lexeme, Form, Sense
from wikibaseintegrator.entities import Item
from wikibaseintegrator.wbi_api import Api

wbi = WikibaseIntegrator()


class TestWbiCore(unittest.TestCase):
    common_item = wbi.item.new().get('Q2')

    def test_item_engine(self):
        Item(api=wbi.api)
        wbi.item.new()
        Item(api=wbi.api).add_claims(String(value='test', prop_nr='P1'))
        Item(api=wbi.api).add_claims([String(value='test', prop_nr='P1')])
        Item(api=wbi.api, id='Q2')
        with self.assertRaises(TypeError):
            Item(api=wbi.api).add_claims('test')

    def test_search_only(self):
        item = wbi.item.new().get(entity_id='Q2')

        assert item.labels.get('en').value == "Earth"

        descr = item.descriptions.get('en').value
        assert len(descr) > 3

        assert "Terra" in item.aliases.get('es')
        assert "planet" in item.descriptions.get('en')

        assert item.labels.get('es') == "Tierra"

    def test_basedatatype_if_exists(self):
        instances = [datatypes.Item(prop_nr='P31', value='Q1234'), datatypes.Item(prop_nr='P31', value='Q1234')]
        item_original = wbi.item.get('Q2')
        len_claims_original = len([x.mainsnak.datavalue['value']['id'] for x in item_original.claims.get('P31')])

        item = deepcopy(item_original)
        item.add_claims(instances, if_exists='APPEND')
        claims = [x.mainsnak.datavalue['value']['id'] for x in item.claims.get('P31')]
        assert len(claims) == len_claims_original + 1 and 'Q1234' in claims and claims.count('Q1234') == 1

        item = deepcopy(item_original)
        item.add_claims(instances, if_exists='FORCE_APPEND')
        claims = [x.mainsnak.datavalue['value']['id'] for x in item.claims.get('P31')]
        assert len(claims) == len_claims_original + 2 and 'Q1234' in claims and claims.count('Q1234') == 2

        item = deepcopy(item_original)
        item.add_claims(instances, if_exists='KEEP')
        claims = [x.mainsnak.datavalue['value']['id'] for x in item.claims.get('P31')]
        assert len(claims) == len_claims_original and 'Q1234' not in claims

        item = deepcopy(item_original)
        item.add_claims(instances, if_exists='REPLACE')
        claims = [x.mainsnak.datavalue['value']['id'] for x in item.claims.get('P31')]
        removed_claims = [True for x in item.claims.get('P31') if x.removed]
        assert len(claims) == len_claims_original + 2 and 'Q1234' in claims and len(removed_claims) == 2 and True in removed_claims

    def test_label(self):
        item = wbi.item.get('Q2')

        assert item.labels.get('en') == "Earth"
        descr = item.descriptions.get('en').value
        pprint(descr)
        assert len(descr) > 3

        assert "Terra" in item.aliases.get('es')
        assert "planet" in item.descriptions.get('en')

        assert item.labels.get("es") == "Tierra"

        # set_description on already existing description
        item.descriptions.set(value=descr)
        assert item.descriptions.get() == descr
        item.descriptions.set(value='fghjkl')
        assert item.descriptions.get() == 'fghjkl'
        item.descriptions.set(value='fghjkltest', language='es')
        assert item.descriptions.get('es') == 'fghjkltest'
        item.descriptions.set(value='fghjkltest', language='en', if_exists='KEEP')
        assert item.get_json()['descriptions']['en'] == {'language': 'en', 'value': 'fghjkl'}
        # set_description on empty desription
        item.descriptions.set(value='')
        item.descriptions.set(value='zaehjgreytret', language='en', if_exists='KEEP')
        assert item.get_json()['descriptions']['en'] == {'language': 'en', 'value': 'zaehjgreytret'}

        item.labels.set(value='Earth')
        item.labels.set(value='xfgfdsg')
        item.labels.set(language='en', value='xfgfdsgtest', if_exists='KEEP')
        assert item.get_json()['labels']['en'] == {'language': 'en', 'value': 'xfgfdsg'}
        assert item.get_json()['labels']['fr'] == {'language': 'fr', 'value': 'Terre'}
        item.aliases.set(values=["fake alias"], if_exists='APPEND')
        assert {'language': 'en', 'value': 'fake alias'} in item.get_json()['aliases']['en']

        item.labels.set(language='fr', value=None)
        item.labels.set(language='non-exist-key', value=None)
        assert 'remove' in item.get_json()['labels']['fr']

        item.labels.set(language='ak')
        item.descriptions.set(language='ak')
        item.aliases.set(language='ak')
        item.labels.set(value='label', language='ak')
        item.descriptions.set(value='d', language='ak')
        item.aliases.set(values=['a'], language='ak', if_exists='APPEND')
        assert item.aliases.get('ak') == ['a']
        item.aliases.set(values='b', language='ak')
        assert item.aliases.get('ak') == ['a', 'b']
        item.aliases.set(values='b', language='ak', if_exists='REPLACE')
        assert item.aliases.get('ak') == ['b']
        item.aliases.set(values=['c'], language='ak', if_exists='REPLACE')
        assert item.aliases.get('ak') == ['c']
        item.aliases.set(values=['d'], language='ak', if_exists='KEEP')
        assert 'd' not in item.aliases.get('ak')
        item.aliases.set(language='ak', if_exists='KEEP')
        assert 'remove' not in item.get_json()['aliases']['ak'][0]
        item.aliases.set(language='ak')
        assert 'remove' in item.get_json()['aliases']['ak'][0]

    def test_wd_search(self):
        t = Api.search_entities('rivaroxaban')
        print('Number of results: ', len(t))
        self.assertIsNot(len(t), 0)

    def test_entity_generator(self):
        entities = ['Q408883', 'P715', 'Q18046452']

        entity_instances = Api.generate_entity_instances(entities=entities)

        for qid, entity in entity_instances:
            self.assertIn(qid, entities)

    def test_new_item_creation(self):
        data = [
            String(value='test1', prop_nr='P1'),
            String(value='test2', prop_nr='1'),
            String(value='test3', prop_nr=1),
            Math("xxx", prop_nr="P2"),
            ExternalID("xxx", prop_nr="P3"),
            datatypes.Item("Q123", prop_nr="P4"),
            datatypes.Item("123", prop_nr="P4"),
            datatypes.Item(123, prop_nr="P4"),
            Time(time='-0458-00-00T00:00:00Z', before=1, after=2, precision=3, timezone=4, prop_nr="P5"),
            Time(time='458-00-00T00:00:00Z', before=1, after=2, precision=3, timezone=4, prop_nr="P5"),
            Time(time='+2021-01-01T15:15:15Z', before=1, after=2, precision=3, timezone=4, prop_nr="P5"),
            URL("http://www.wikidata.org", prop_nr="P6"),
            URL("https://www.wikidata.org", prop_nr="P6"),
            URL("ftp://example.com", prop_nr="P6"),
            URL("ssh://user@server/project.git", prop_nr="P6"),
            URL("svn+ssh://user@server:8888/path", prop_nr="P6"),
            MonolingualText(text="xxx", language="fr", prop_nr="P7"),
            Quantity(quantity=-5.04, prop_nr="P8"),
            Quantity(quantity=5.06, upper_bound=9.99, lower_bound=-2.22, unit="Q11573", prop_nr="P8"),
            CommonsMedia("xxx", prop_nr="P9"),
            GlobeCoordinate(latitude=1.2345, longitude=-1.2345, precision=12, prop_nr="P10"),
            GeoShape("Data:xxx.map", prop_nr="P11"),
            Property("P123", prop_nr="P12"),
            Property("123", prop_nr="P12"),
            Property(123, prop_nr="P12"),
            TabularData("Data:Taipei+Population.tab", prop_nr="P13"),
            MusicalNotation("\relative c' { c d e f | g2 g | a4 a a a | g1 |}", prop_nr="P14"),
            Lexeme("L123", prop_nr="P15"),
            Lexeme("123", prop_nr="P15"),
            Lexeme(123, prop_nr="P15"),
            Form("L123-F123", prop_nr="P16"),
            Sense("L123-S123", prop_nr="P17")
        ]

        for d in data:
            item = wbi.item.new().add_claims([d])
            assert item.get_json()
            item = wbi.item.new().add_claims(d)
            assert item.get_json()

        item = wbi.item.new().add_claims(data)
        pprint(item.get_json())
        assert item.get_json()

    def test_get_property_list(self):
        self.assertTrue(len(self.common_item.claims))

    def test_count_references(self):
        self.assertTrue(len(self.common_item.claims.get('P2067')[0].references))

    def test_get_qualifier_properties(self):
        self.assertTrue(len(self.common_item.claims.get(property='P2067')))
