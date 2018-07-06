from pyparsing import Word, Suppress, Literal, Group, Optional, OneOrMore, Forward
import string

def get_parser(types):
    TYPE = Literal(types[0])
    for tp in types[1:]:
        TYPE = (TYPE | Literal(tp))

    VALUE = Word(''.join((set(string.printable).difference(set('<>|')))))

    OPEN = Suppress('<')
    CLOSE = Suppress('>')
    DELIMITER = Suppress('|')
    LIST_DELIMITER = Suppress(Optional(','))
    DICT_DELIMITER = Suppress(':')

    SINGLE = OPEN + TYPE + DELIMITER + VALUE + DELIMITER + CLOSE
    COMBI = Forward()
    DICT_VALUE = Group(
        OneOrMore(
            Group(Group(COMBI) + DICT_DELIMITER + Group(COMBI) + LIST_DELIMITER)
        ))
    NESTED_VALUE = Group(OneOrMore(Group(COMBI + LIST_DELIMITER)))
    COMBI << OPEN + TYPE + DELIMITER + (VALUE | DICT_VALUE | NESTED_VALUE) + DELIMITER + CLOSE

    return COMBI
