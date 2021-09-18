import simplejson

from wikibaseintegrator.datatypes import BaseDataType
from wikibaseintegrator.models.claims import Claims, Claim
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import ActionIfExists
from wikibaseintegrator.wbi_exceptions import NonUniqueLabelDescriptionPairError, MWApiError
from wikibaseintegrator.wbi_fastrun import FastRunContainer
from wikibaseintegrator.wbi_helpers import mediawiki_api_call_helper


class BaseEntity:
    fast_run_store = []

    ETYPE = 'base-entity'

    def __init__(self, api, lastrevid=None, type=None, id=None, claims=None):
        self.api = api

        self.lastrevid = lastrevid
        self.type = type or self.ETYPE
        self.id = id
        self.claims = claims or Claims()

        self.json = {}

        self.fast_run_container = None

        self.debug = config['DEBUG']

    def add_claims(self, claims, action_if_exists=ActionIfExists.APPEND):
        if isinstance(claims, Claim):
            claims = [claims]
        elif not isinstance(claims, list):
            raise TypeError()

        self.claims.add(claims=claims, action_if_exists=action_if_exists)

        return self

    def get_json(self) -> {}:
        json_data = {
            'type': self.type,
            'id': self.id,
            'claims': self.claims.get_json()
        }
        if self.type == 'mediainfo':  # MediaInfo change name of 'claims' to 'statements'
            json_data['statements'] = json_data.pop('claims')
        if not self.id:
            del json_data['id']

        return json_data

    def from_json(self, json_data):
        self.json = json_data

        if 'missing' in json_data:
            raise ValueError('Entity is nonexistent')

        self.lastrevid = json_data['lastrevid']
        self.type = json_data['type']
        self.id = json_data['id']
        if self.type == 'mediainfo':  # 'claims' is named 'statements' in Wikimedia Commons MediaInfo
            self.claims = Claims().from_json(json_data['statements'])
        else:
            self.claims = Claims().from_json(json_data['claims'])

    def get(self, entity_id, **kwargs):
        """
        retrieve an item in json representation from the Wikibase instance
        :rtype: dict
        :return: python complex dictionary representation of a json
        """

        params = {
            'action': 'wbgetentities',
            'ids': entity_id,
            'format': 'json'
        }

        return self.api.helpers.mediawiki_api_call_helper(data=params, allow_anonymous=True, **kwargs)

    def clear(self, **kwargs):
        self._write(clear=True, **kwargs)

    def _write(self, data=None, summary=None, allow_anonymous=False, clear=False, **kwargs):
        """
        Writes the item Json to the Wikibase instance and after successful write, updates the object with new ids and hashes generated by the Wikibase instance.
        For new items, also returns the new QIDs.
        :param allow_anonymous: Allow anonymous edit to the MediaWiki API. Disabled by default.
        :type allow_anonymous: bool
        :return: the entity ID on successful write
        """

        data = data or {}

        # if all_claims:
        #     data = json.JSONEncoder().encode(self.json_representation)
        # else:
        #     new_json_repr = {k: self.json_representation[k] for k in set(list(self.json_representation.keys())) - {'claims'}}
        #     new_json_repr['claims'] = {}
        #     for claim in self.json_representation['claims']:
        #         if [True for x in self.json_representation['claims'][claim] if 'id' not in x or 'remove' in x]:
        #             new_json_repr['claims'][claim] = copy.deepcopy(self.json_representation['claims'][claim])
        #             for statement in new_json_repr['claims'][claim]:
        #                 if 'id' in statement and 'remove' not in statement:
        #                     new_json_repr['claims'][claim].remove(statement)
        #             if not new_json_repr['claims'][claim]:
        #                 new_json_repr['claims'].pop(claim)
        #     data = json.JSONEncoder().encode(new_json_repr)

        data = simplejson.JSONEncoder().encode(data)

        payload = {
            'action': 'wbeditentity',
            'data': data,
            'format': 'json',
            'summary': summary
        }

        if not summary:
            payload.pop('summary')

        if self.api.is_bot:
            payload.update({'bot': ''})

        if clear:
            payload.update({'clear': True})

        if self.id:
            payload.update({'id': self.id})
        else:
            payload.update({'new': self.type})

        if self.lastrevid:
            payload.update({'baserevid': self.lastrevid})

        if self.debug:
            print(payload)

        try:
            json_data = mediawiki_api_call_helper(data=payload, login=self.api.login, allow_anonymous=allow_anonymous, is_bot=self.api.is_bot, **kwargs)

            if 'error' in json_data and 'messages' in json_data['error']:
                error_msg_names = {x.get('name') for x in json_data['error']['messages']}
                if 'wikibase-validator-label-with-description-conflict' in error_msg_names:
                    raise NonUniqueLabelDescriptionPairError(json_data)

                raise MWApiError(json_data)

            if 'error' in json_data.keys():
                raise MWApiError(json_data)
        except Exception:
            print('Error while writing to the Wikibase instance')
            raise

        # after successful write, update this object with latest json, QID and parsed data types.
        self.id = json_data['entity']['id']
        if 'success' in json_data and 'entity' in json_data and 'lastrevid' in json_data['entity']:
            self.lastrevid = json_data['entity']['lastrevid']
        return json_data['entity']

    def init_fastrun(self, base_filter=None, use_refs=False, case_insensitive=False):
        if base_filter is None:
            base_filter = {}

        if self.debug:
            print('Initialize Fast Run init_fastrun')
        # We search if we already have a FastRunContainer with the same parameters to re-use it
        for fast_run in BaseEntity.fast_run_store:
            if (fast_run.base_filter == base_filter) and (fast_run.use_refs == use_refs) and (fast_run.case_insensitive == case_insensitive) and (
                    fast_run.sparql_endpoint_url == config['SPARQL_ENDPOINT_URL']):
                self.fast_run_container = fast_run
                self.fast_run_container.current_qid = ''
                self.fast_run_container.base_data_type = BaseDataType
                if self.debug:
                    print("Found an already existing FastRunContainer")

        if not self.fast_run_container:
            if self.debug:
                print("Create a new FastRunContainer")
            self.fast_run_container = FastRunContainer(base_filter=base_filter,
                                                       use_refs=use_refs,
                                                       base_data_type=BaseDataType,
                                                       case_insensitive=case_insensitive)
            BaseEntity.fast_run_store.append(self.fast_run_container)

    def fr_search(self, **kwargs):
        self.init_fastrun(**kwargs)
        self.fast_run_container.load_item(self.claims)

        return self.fast_run_container.current_qid

    def write_required(self, base_filter=None, **kwargs):
        self.init_fastrun(base_filter=base_filter, **kwargs)

        if base_filter is None:
            base_filter = {}

        claims_to_check = []
        for claim in self.claims:
            if claim.mainsnak.property_number in base_filter:
                claims_to_check.append(claim)

        return self.fast_run_container.write_required(data=claims_to_check, cqid=self.id)

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs="\r\n\t ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )
