import datajoint as dj
import dash_table
import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import copy
from . import dj_utils
import re

table_style_template = dict(
    style_cell={
        'textAlign': 'left',
        'fontSize': 12,
        'font-family': 'helvetica',
        'minWidth': '120px', 'width': '120px', 'maxWidth': '120px',
        'height': '30px'
        },
    page_action='none',
    style_table={
        'minWidth': '1200px',
        'width': '1200px',
        'maxWidth': '1200px',
        'overflowX': 'auto'},
    style_header={
        'backgroundColor': 'rgb(220, 220, 220)',
        'fontWeight': 'bold'})


def create_display_table(
        table, table_id=None,
        height='900px', width=None,
        selectable=True, excluded_fields=[],
        empty_first=False, data=None):

    if not table_id:
        table_id = table.__name__.lower()

    table_style = copy.deepcopy(table_style_template)
    table_style.update(
        fixed_columns={'headers': True, 'data': 1},
        # allow sorting
        sort_action='native',
        # allow filtering
        filter_action='native',
    )

    if selectable:
        table_style.update(
            # allow selecting a single entry
            row_selectable='single'
        )

    columns = [{"name": i, "id": i}
               for i in table.heading.names if i not in excluded_fields]

    if not width:
        width = f'{min([120 * len(columns), 400])}px'

    table_style['style_table'].update(
        {
            'minHeight': height,
            'height': height,
            'maxHeight': height,
            'minWidth': width,
            'width': width,
            'maxWidth': width
        }
    )
    table_style['style_cell'].update(
        {
            'textAlign': 'left',
            'fontSize': 12,
            'font-family': 'helvetica',
            'minWidth': '120px', 'width': '120px', 'maxWidth': '120px',
            'height': 'auto',
            'whiteSpace': 'normal'
        }
    )

    if empty_first:
        data = [{c['id']: '' for c in columns}]
    elif data is None:
        data = table.fetch(as_dict=True)

    return dash_table.DataTable(
        id=table_id,
        columns=columns,
        data=data,
        **table_style,
    )


def create_edit_record_table(
        table, table_id,
        dropdown_fields=[], excluded_fields=[],
        height='100px', width='1200px',
        n_rows=1,
        pk_editable=False,
        deletable=False,
        defaults={}):

    if not dropdown_fields:
        dropdown_fields = dj_utils.get_dropdown_fields(table)

    dropdown_fields = [f for f in dropdown_fields if f not in excluded_fields]

    required_fields = dj_utils.get_required_fields(table)

    table_style = copy.deepcopy(table_style_template)
    table_style['style_table'].update(
        {
            'minHeight': height,
            'height': height,
            'maxHeight': height,
            'minWidth': width,
            'width': width,
            'maxWidth': width
        }
    )
    table_style['style_cell'].update(
        {
            'textAlign': 'left',
            'fontSize': 12,
            'font-family': 'helvetica',
            'minWidth': '120px', 'width': '120px', 'maxWidth': '120px',
            'height': 'auto',
            'whiteSpace': 'normal'
        }
    )
    heading = table.heading
    columns = [{'name': i, 'id': i}
               for i in heading.names if i not in excluded_fields]
    # contruct a comprehensive name of column
    for c in columns:
        if c['id'] in required_fields:
            c['name'] = c['name'] + '*'
        # add data type
        dtype = heading.attributes[c['id']].type
        # if there is unit
        unit = re.search(r'^\((.+)\)', heading.attributes[c['id']].comment)
        if unit:
            dtype = dtype + f'; {unit.group(1)}'

        c['name'] = c['name'] + f' ({dtype})'

    # some fields are presented as dropdown list
    if dropdown_fields:
        for c in columns:
            if c['id'] in dropdown_fields:
                c.update(presentation="dropdown")

    for c in columns:
        if c['id'] in heading.primary_key and not pk_editable:
            c.update(editable=False)
        else:
            c.update(editable=True)

    return dash_table.DataTable(
        id=table_id,
        columns=columns,
        data=[{c['id']: defaults[c['id']] if c['id'] in defaults.keys()
               else dj_utils.get_default(table, c['id'])
              for c in columns}] * n_rows,
        persistence=True,
        **table_style,
        dropdown={
            f:
            {
                'options': [{'label': i, 'value': i}
                            for i in dj_utils.get_options(table, f)]
            }
            for f in dropdown_fields
        },
        row_deletable=deletable
    )


def create_modal(table, id=None, dropdown_fields=[], extra_tables=[],
                 mode='add', defaults={}):

    if not id:
        id = table.__name__.lower()

    if not dropdown_fields:
        dropdown_fields = dj_utils.get_dropdown_fields(table)

    master_table = create_edit_record_table(
        table, f'{mode}-{id}-table',
        dropdown_fields=dropdown_fields,
        height='200px', width='800px',
        pk_editable=mode != 'update',
        defaults=defaults)

    # TODO: allow defaults in part table as well
    if extra_tables:
        part_tables = []
        for p in extra_tables:
            part_tables.append(
                html.Div(
                    id=f'{mode}-{table.__name__.lower()}-{p.__name__.lower()}-table-div',
                    children=[
                        html.H6(f'{p.__name__}'),
                        html.Button(
                            'Add a row',
                            id=f'{mode}-{table.__name__.lower()}-{p.__name__.lower()}-add-row-button',
                            style={
                                    'display': 'block',
                                    'width': '150px',
                                    'height': '40px',
                                    'marginBottom': '0.5em'
                                }
                            ),
                        create_edit_record_table(
                            p, f'{mode}-{table.__name__.lower()}-{p.__name__.lower()}-table',
                            excluded_fields=table.heading.primary_key,
                            height='100px', width='370px',
                            pk_editable=True, deletable=True),
                    ],
                    style={'marginLeft': '1em'}
                ),
            )
        tables = [master_table, dbc.Row(part_tables)]
    else:
        tables = [master_table]

    message_box = dcc.Textarea(
        id=f'{mode}-{id}-message',
        value=f'{mode.capitalize()} message:',
        style={'width': 250, 'height': 200, 'marginLeft': '2em'}
    )

    return dbc.Modal(
        [
            dbc.ModalHeader(f'{mode.capitalize()} {table.__name__} record'),
            dbc.Row([dbc.Col(
                        tables, width=8),
                     dbc.Col(message_box, width=4)]),
            dbc.ModalFooter(
                [
                    dbc.Button(f'{mode.capitalize()} record', id=f'{mode}-{id}-confirm',
                               className='ml-auto'),
                    dbc.Button('Close', id=f'{mode}-{id}-close', className='ml-auto')
                ]
            ),
        ],
        id=f'{mode}-{id}-modal',
        size='xl',
    )


def create_filter_dropdown(table, id, field, width='200px'):

    return dcc.Dropdown(
        id=id,
        options=[
            {'label': f, 'value': f}
            for f in (dj.U(field) & table).fetch(field)
        ],
        style={'width': width, 'marginBottom': '0.5em'},
        placeholder='Select {} ...'.format(field),
    )
