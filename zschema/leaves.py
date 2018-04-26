import sys
import unittest
import re
import dateutil.parser
import datetime
import socket

from keys import *

class Leaf(Keyable):

    DEPRECATED = False
    INCLUDE_RAW = False

    def __init__(self,
            required=False,
            es_index=None,
            es_analyzer=None,
            doc=None,
            examples=None,
            es_include_raw=None,
            deprecated=False,
            ignore=False,
            category=None,
            exclude=None,
            metadata=None,
            units=None,
            min_value=None,
            max_value=None,
            validator=None):
        self.required = required
        self.es_index = es_index
        self.es_analyzer = es_analyzer
        self.doc = doc
        self.examples = examples if examples else []
        if es_include_raw is not None:
            self.es_include_raw = es_include_raw
        else:
            self.es_include_raw = self.INCLUDE_RAW
        self.deprecated = deprecated
        self.ignore = ignore
        if self.DEPRECATED:
            e = "WARN: %s is deprecated and will be removed in a "\
                    "future release\n" % self.__class__.__name__
            sys.stderr.write(e)
        self.category = category
        self._exclude = set(exclude) if exclude else set([])
        self.metadata = metadata if metadata else {}
        self.units = units
        self.min_value = min_value
        self.max_value = max_value
        self.validator = validator

    def to_dict(self):
        retv = {
            "required":self.required,
            "doc":self.doc,
            "type":self.__class__.__name__,
            "es_type":self.ES_TYPE,
            "bq_type":self.BQ_TYPE,
            "metadata":self.metadata,
            "examples": self.examples,
        }
        if self.units is not None:
            retv["units"] = self.units
        self.add_es_var(retv, "es_analyzer", "es_analyzer", "ES_ANALYZER")
        self.add_es_var(retv, "es_index", "es_index", "ES_INDEX")
        self.add_es_var(retv, "es_search_analyzer", "es_search_analyzer",
                "ES_SEARCH_ANALYZER")
        return retv

    def to_es(self):
        retv = {"type":self.ES_TYPE}
        self.add_es_var(retv, "index", "es_index", "ES_INDEX")
        self.add_es_var(retv, "analyzer", "es_analyzer", "ES_ANALYZER")
        self.add_es_var(retv, "search_analyzer", "es_search_analyzer",
                "ES_SEARCH_ANALYZER")
        if self.es_include_raw:
            retv["fields"] = {
                    "raw":{"type":"keyword"}
            }
        return retv

    def _docs_common(self, parent_category):
        retv = {
            "detail_type": self.__class__.__name__,
            "category": self.category or parent_category,
            "doc": self.doc,
            "required": self.required,
            "examples": self.examples,
        }
        return retv

    def docs_es(self, parent_category=None):
        retv = self._docs_common(parent_category)
        self.add_es_var(retv, "analyzer", "es_analyzer", "ES_ANALYZER")
        retv["type"] = self.ES_TYPE
        return retv

    def docs_bq(self, parent_category=None):
        retv = self._docs_common(parent_category)
        retv["type"] = self.BQ_TYPE
        return retv

    def to_bigquery(self, name):
        if not self._check_valid_name(name):
            raise Exception("Invalid field name: %s" % name)
        mode = "REQUIRED" if self.required else "NULLABLE"
        retv = {"name":self.key_to_bq(name), "type":self.BQ_TYPE, "mode":mode}
        if self.doc:
            retv["doc"] = self.doc
        return retv

    def to_string(self, name):
        return "%s: %s" % (self.key_to_string(name),
                           self.__class__.__name__.lower())

    def to_flat(self, parent, name, repeated=False):
        if not self._check_valid_name(name):
            raise Exception("Invalid field name: %s" % name)
        if repeated:
            mode = "repeated"
        elif self.required:
            mode = "required"
        else:
            mode = "nullable"
        full_name = ".".join([parent, name]) if parent else name
        yield {
            "name":full_name,
            "type":self.__class__.__name__,
            "es_type": self.ES_TYPE,
            "documentation":self.doc,
            "mode":mode
        }
        if self.es_include_raw:
            yield {
                "name":full_name + ".raw",
                "type":self.__class__.__name__,
                "documentation":self.doc,
                "es_type": self.ES_TYPE,
                "mode":mode
            }

    def print_indent_string(self, name, indent):
        val = self.key_to_string(name)
        if indent:
            tabs = "\t" * indent
            val = tabs + val
        print val

    def validate(self, name, value):
        if self.validator:
            self.validator.validate(name, value)
            return
        if not self._check_valid_name(name):
            raise DataValidationException("Invalid field name: %s" % name)
        if value is None:
            if self.required:
                raise DataValidationException("%s is a required field, but "
                                              "recieved None" % name)
            else:
                return
        if type(value) not in self.EXPECTED_CLASS:
            m = "class mismatch for %s: expected %s, %s has class %s" % (\
                    self.key_to_string(name), self.EXPECTED_CLASS,
                    str(value), value.__class__.__name__)
            raise DataValidationException(m)
        if hasattr(self, "_validate"):
            self._validate(str(name), value)



class String(Leaf):

    ES_TYPE = "keyword"
    BQ_TYPE = "STRING"
    EXPECTED_CLASS = [str,unicode]

    INVALID = 23
    VALID = "asdf"


class EnglishString(Leaf):

    ES_TYPE = "text"
    BQ_TYPE = "STRING"
    ES_ANALYZER = "standard"
    EXPECTED_CLASS = [str,unicode]

    INVALID = 23
    VALID = "asdf"


class AnalyzedString(Leaf):

    ES_TYPE = "text"
    BQ_TYPE = "STRING"
    ES_ANALYZER = "simple"
    EXPECTED_CLASS = [str,unicode]

    INVALID = 23
    VALID = "asdf"


class WhitespaceAnalyzedString(AnalyzedString):
    """
    curl -XPUT 'localhost:9200/YOUR-INDEX-HERE/_settings' -d '{
      "analysis" : {
        "analyzer":{
          "lower_whitespace":{
            "type":"custom",
            "tokenizer":"whitespace",
            "filter":["lowercase"]
          }
        }
      }
    }'
    """
    ES_ANALYZER="lower_whitespace"


class HexString(Leaf):

    ES_TYPE = "keyword"
    BQ_TYPE = "STRING"
    EXPECTED_CLASS = [str,unicode]

    INVALID = "asdfasdfa"
    VALID = "003a929e3e0bd48a1e7567714a1e0e9d4597fe9087b4ad39deb83ab10c5a0278"

    #ES_SEARCH_ANALYZER = "lower_whitespace"
    HEX_REGEX = re.compile('(?:[A-Fa-f0-9][A-Fa-f0-9])+')

    def _is_hex(self, s):
        return bool(self.HEX_REGEX.match(s))

    def _validate(self, name, value):
        if not self._is_hex(value):
            m = "%s: the value %s is not hex" % (name, value)
            raise DataValidationException(m)


class Enum(Leaf):

    ES_TYPE = "keyword"
    BQ_TYPE = "STRING"

    EXPECTED_CLASS = [str,unicode]

    INVALID = 23
    VALID = None

    def __init__(self, values=None, *args, **kwargs):
        Leaf.__init__(self, *args, **kwargs)
        if values is None:
            values = []
        self.values = values
        self.values_s = set(values)

    def _validate(self, name, value):
        if len(self.values_s) and value not in self.values_s:
            m = "%s: the value %s is not a valid enum option" % (name, value)
            raise DataValidationException(m)

    def _docs_common(self, parent_category):
        retv = super(Enum, self)._docs_common(parent_category)
        if len(self.values_s):
            retv["values"] = list(self.values_s)
            del retv["examples"]
        return retv

class HTML(AnalyzedString):

    """
    curl -XPUT 'localhost:9200/ipv4/_settings' -d '{
      "analysis" : {
        "analyzer":{
          "html":{
            "type":"custom",
            "tokenizer":"standard",
            "char_filter":[ "html_strip"]
          }
        }
      }
    }'
    """
    ES_ANALYZER = "html"


class IPAddress(Leaf):

    ES_TYPE = "ip"
    BQ_TYPE = "STRING"
    EXPECTED_CLASS = [str,unicode]

    IPV4_REGEX = re.compile('(\d{1,3}\.){3}\d{1,3}')

    def _is_ipv4_addr(self, ip):
        return bool(self.IPV4_REGEX.match(ip))

    def _is_ipv6_addr(self, ip):
        try:
            socket.inet_pton(socket.AF_INET6, ip)
            return True
        except socket.error:
            return False

    def _validate(self, name, value):
        if not self._is_ipv4_addr(value) and not self._is_ipv6_addr(value):
            m = "%s: the value %s is not a valid IP address" % (name, value)
            raise DataValidationException(m)


class IPv4Address(IPAddress):

    INVALID = "my string"
    VALID = "141.212.120.0"

    def _validate(self, name, value):
        if not self._is_ipv4_addr(value):
            m = "%s: the value %s is not a valid IPv4 address" % (name, value)
            raise DataValidationException(m)


class IPv6Address(IPAddress):

    INVALID = "my string"
    VALID = "2a04:9740:8:c010:e228:6dff:fefe:6e53"

    def _validate(self, name, value):
        if not self._is_ipv6_addr(value):
            m = "%s: the value %s is not a valid IPv6 address" % (name, value)
            raise DataValidationException(m)


class _Integer(Leaf):

    ES_TYPE = "integer"
    BQ_TYPE = "INTEGER"

    EXPECTED_CLASS = [int,]

    def _validate(self, name, value):
        max_ = 2**self.BITS - 1
        min_ = -2**self.BITS + 1
        if value > max_:
            raise DataValidationException("%s: %s is larger than max (%s)" % (\
                    name, str(value), str(max_)))
        if value < min_:
            raise DataValidationException("%s: %s is smaller than min (%s)" % (\
                    name, str(value), str(min_)))


class Signed32BitInteger(_Integer):

    INVALID = 8589934592
    VALID = 234234252

    BITS = 32


class Signed8BitInteger(_Integer):

    ES_TYPE = "byte"
    BITS = 8
    INVALID = 2**8+5
    VALID = 34


class Signed16BitInteger(_Integer):

    ES_TYPE = "short"
    BITS = 16
    INVALID = 2**16
    VALID = 0xFFFF
    EXPECTED_CLASS = [int,]


class Unsigned8BitInteger(Signed16BitInteger):
    pass


class Unsigned16BitInteger(Signed32BitInteger):
    pass


class Signed64BitInteger(_Integer):

    ES_TYPE = "long"
    BQ_TYPE = "INTEGER"
    EXPECTED_CLASS = [int,long]
    INVALID = 2l**68
    VALID = 10l
    BITS = 64


class Unsigned32BitInteger(Signed64BitInteger):
    pass


class Float(Leaf):

    ES_TYPE = "float"
    BQ_TYPE = "FLOAT"
    EXPECTED_CLASS = [float,]
    INVALID = "I'm a string!"
    VALID = 10.0


class Double(Float):

    ES_TYPE = "double"
    BQ_TYPE = "FLOAT"
    EXPECTED_CLASS = [float,]


class Boolean(Leaf):

    ES_TYPE = "boolean"
    BQ_TYPE = "BOOLEAN"
    EXPECTED_CLASS = [bool,]
    INVALID = 0
    VALID = True


class Binary(Leaf):

    ES_TYPE = "binary"
    BQ_TYPE = "STRING"
    ES_INDEX = "no"
    EXPECTED_CLASS = [str,unicode]
    B64_REGEX = re.compile('^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$')

    def _is_base64(self, data):
        return bool(self.B64_REGEX.match(data))

    def _validate(self, name, value):
        if not self._is_base64(value):
            m = "%s: the value %s is not valid Base64" % (name, value)
            raise DataValidationException(m)

    VALID = "03F87824"
    INVALID = "normal"


class IndexedBinary(Binary):

    ES_TYPE = "string"
    BQ_TYPE = "STRING"
    ES_INDEX = "not_analyzed"


class DateTime(Leaf):

    ES_TYPE = "date"
    BQ_TYPE = "DATETIME"
    # dateutil.parser.parse(int) throws...? is this intended to be a unix epoch offset?
    EXPECTED_CLASS = [str, int, unicode, datetime.datetime]

    VALID = "Wed Jul  8 08:52:01 EDT 2015"
    INVALID = "Wed DNE  35 08:52:01 EDT 2015"

    MIN_VALUE = "1753-01-01 00:00:00.000000"
    MAX_VALUE = "9999-12-31 00:00:00.000000"

    def __init__(self, *args, **kwargs):
        super(DateTime, self).__init__(*args, **kwargs)

        if self.min_value:
            self._min_value_dt = dateutil.parser.parse(self.min_value, ignoretz=True)
        else:
            self._min_value_dt = dateutil.parser.parse(self.MIN_VALUE, ignoretz=True)

        if self.max_value:
            self._max_value_dt = dateutil.parser.parse(self.max_value, ignoretz=True)
        else:
            self._max_value_dt = dateutil.parser.parse(self.MAX_VALUE, ignoretz=True)

    def _validate(self, name, value):
        if isinstance(value, datetime.datetime):
            dt = value
        elif isinstance(value, int):
            dt = datetime.datetime.utcfromtimestamp(value)
        else:
            # FIXME: ignoretz should be set for TIMESTAMP but not DATETIME?
            try:
                dt = dateutil.parser.parse(value, ignoretz=True)
            except Exception, e:
                m = "%s: %s is not valid timestamp" % (name, str(value))
                raise DataValidationException(m)
        if dt > self._max_value_dt:
            m = "%s: %s is larger than allowed maximum (%s)" % (name,
                    str(value), str(self._max_value_dt))
            raise DataValidationException(m)
        if dt < self._min_value_dt:
            m = "%s: %s is larger than allowed minimum (%s)" % (name,
                    str(value), str(self._min_value_dt))
            raise DataValidationException(m)


class Timestamp(DateTime):

    BQ_TYPE = "TIMESTAMP"


class OID(String):

    VALID = "1.3.6.1.4.868.2.4.1"
    INVALID = "hello"

    OID_REGEX = re.compile("[[0-9]+\\.]*")

    def _is_oid(self, data):
        return bool(self.OID_REGEX.match(data))

    def _validate(self, name, value):
        if not self._is_oid(value):
            m = "%s: the value %s is not a valid oid" % (name, value)
            raise DataValidationException(m)


class EmailAddress(WhitespaceAnalyzedString):

    INCLUDE_RAW = True


class URL(AnalyzedString):

    # This depends on https://github.com/jlinn/elasticsearch-analysis-url being installed

    """
    curl -XPUT 'localhost:9200/YOUR-INDEX-HERE/_settings' -d '{
      "analysis" : {
        "filter":{
          "url":{
            "type":"url",
            "part":null,
            "url_decode":true,
            "allow_malformed":true,
            "tokenize_malformed":true
          }
        }
      }
    }'
    curl -XPUT 'localhost:9200/YOUR-INDEX-HERE/_settings' -d '{
      "analysis" : {
        "analyzer":{
          "url":{
            "type":"custom",
            "tokenizer":"whitespace",
            "filter":["url"]
          }
        }
      }
    }'

    """

    ES_ANALYZER = "URL"
    ES_SEARCH_ANALYZER = "whitespace"
    INCLUDE_RAW = True


class FQDN(URL):
    pass


class URI(URL):
    pass


VALID_LEAVES = [
    DateTime,
    AnalyzedString,
    String,
    Binary,
    IndexedBinary,
    Boolean,
    Double,
    Float,
    IPv4Address,
    IPv6Address,
    IPAddress,
    Enum,
    HexString,
    OID,
    FQDN,
    URL,
    URI,
    EmailAddress,
]

