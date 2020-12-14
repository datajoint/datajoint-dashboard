import datajoint as dj
import re
import inspect
import datetime
import itertools


def get_dropdown_fields(table):
    graph = table.connection.dependencies
    graph.load()
    foreign_keys = graph.parents(table.full_table_name)

    return list(itertools.chain.from_iterable(
        [list(fk.get('attr_map').keys())
         for fk in foreign_keys.values()])) + \
           [f for f in table.heading.names
            if 'enum' in table.heading.attributes[f].type]


def get_options(table, field, context=None):
    '''
    For a given table and field, return the options of this field.
    Either from a enum or from the foreign keys.
    Inputs: table: table object
            field: str, field name
            context: context to search the class for the table
    Output: a list of possible values of this field, return empty list if there is no options
    '''
    if not context:
        context = {}
        backframe = inspect.currentframe().f_back
        while backframe:
            context.update(backframe.f_globals)
            backframe = backframe.f_back

    inspect.currentframe().f_locals.update(**context)

    dtype = table.heading.attributes[field].type
    # check whether the current field is an enum field.
    if 'enum' in dtype:
        return re.findall(r"'(.*?)'", dtype)

    else:
        graph = table.connection.dependencies
        graph.load()
        foreign_keys = graph.parents(table.full_table_name)

        for key, value in foreign_keys.items():
            dependent_fields = [key_pairs[0] for key_pairs in list(value['attr_map'].items())]
            if field in dependent_fields:
                try:
                    int(key)
                    parent_table_name = list(graph.parents(key).keys())[0]
                    parent_field = list(
                        list(graph.parents(key).values())[0]['attr_map'].items())[dependent_fields.index(field)][1]
                except ValueError:
                    parent_table_name = key
                    parent_field = [v for v in value['attr_map'].values()][dependent_fields.index(field)]
                break

        parent_table = dj.table.lookup_class_name(
            parent_table_name, context
        )

        if not parent_table:
            return []
        options = (dj.U(parent_field) & eval(parent_table)).fetch(parent_field)

        if not len(options):
            options = []
        return list(options)


def get_default(query, field):
    '''
    For a given table and field, return the options of this field.
    Inputs: table: query object
            field: str, field name
    Output: number or string, the default value of this field
    '''
    default = query.heading.attributes[field].default

    if default:
        matches = re.findall(r'\"(.+?)\"', query.heading.attributes[field].default)
        if matches:
            if matches[0] == 'current_timestamp()':
                return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            else:
                return matches[0]
        else:
            return ''
    else:
        return ''
