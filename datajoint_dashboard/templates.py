import datajoint as dj
from datajoint.diagram import _get_tier
import dash
from dash.dependencies import Input, Output, State
import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc
from . import dj_utils, component_utils, callback_utils
import warnings


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


DataJointTable = dj.user_tables.OrderedClass


class Filter:
    def __init__(self, table, field_name,
                 query_function,
                 filter_id=None,
                 default_value=None,
                 multi=False,
                 filter_style=None):
        """Filter object that is able to update its options

        Args:
            name ([type]): [description]
            table ([type]): [description]
        """
        self.query = {}
        self.table = table
        self.field_name = field_name
        self.query_function = query_function
        self.filter_id = filter_id if filter_id else field_name + '-filter'

        self.options = (dj.U(self.field_name) & self.table).fetch(
            self.field_name)
        self.default_value = default_value
        self.layout = dcc.Dropdown(
            id=self.filter_id,
            options=[{'label': i, 'value': i} for i in self.options],
            value=self.default_value,
            style={'width': '200px', 'marginBottom': '0.5em'},
            placeholder=f'Select {field_name}...',
            multi=multi
        )

    @property
    def get_options(self, query):
        return (dj.U(self.name) &
                (self.table & query)).fetch(self.name)

    def update_query(self, values):
        self.query = self.query_function(self.table, values)


class FilterCollection:
    def __init__(self, filters: list):

        self.filters = {f.filter_id: f for f in filters}
        self.layout = html.Div(
            [f.layout for f in self.filters.values()],
            style={'display': 'inline-block'}
        )

    def apply_filters(self, table: DataJointTable):
        query = table
        for f in self.filters.values():
            query = query & f.query
        return query


class TableBlock:
    def __init__(self, table: DataJointTable, app=None, extra_tables=[],
                 table_height='800px',
                 table_width='800px',
                 button_style={
                    'marginRight': '1em',
                    'marginBottom': '1em'},
                 messagebox_style={
                    'width': 750,
                    'height': 50,
                    'marginBottom': '1em',
                    'display': 'block'},
                 defaults={},
                 filters=[]
                 ):
        self.app = app
        self.table = table
        self.main_table_data = table.fetch(as_dict=True)
        self.table_name = table.__name__.lower()
        self.table_original_name = table.__name__
        self.primary_key = table.heading.primary_key
        self.attrs = table.heading.attributes
        self.field_names = table.heading.names
        self.schema_name = table.database
        self.table_is_part = _get_tier(self.table.full_table_name) == dj.user_tables.Part
        if self.table_is_part:
            self.master_name = self.table._master.__name__
        self.refreshed = 0
        self.table_height = table_height
        self.table_width = table_width
        self.defaults = defaults

        if filters:
            self.filter_collection = FilterCollection(filters)
            self.filter_collection_layout = self.filter_collection.layout
        else:
            self.filter_collection = AttrDict(filters={})
            self.filter_collection_layout = html.Div()

        # validate the extra tables
        self.valid_extra_tables = []
        for t in extra_tables:
            if all([k in t.heading.primary_key for k in self.primary_key]):
                self.valid_extra_tables.append(t)
            else:
                warnings.warn(
                    f'Extra table {t} is not bound to the master table, \
                      ignored in display.')

        # fixed elements
        self.add_button = html.Button(
            children=f'Add a {self.table_name} record',
            id=f'add-{self.table_name}-button', n_clicks=0,
            style=button_style)

        self.delete_button = html.Button(
            children='Delete the current record',
            id=f'delete-{self.table_name}-button', n_clicks=0,
            style=button_style
        )

        self.update_button = html.Button(
            children='Update the current record',
            id=f'update-{self.table_name}-button', n_clicks=0,
            style=button_style
        )

        self.delete_message_box = dcc.Textarea(
            id=f'delete-{self.table_name}-message-box',
            value=f'Delete {self.table.__name__} record message:',
            style=messagebox_style
        )

        self.delete_confirm = dcc.ConfirmDialog(
            id=f'delete-{self.table_name}-confirm',
            message='Are you sure to delete the record?',
        )

        self.add_modal = component_utils.create_modal(
            self.table, self.table_name, extra_tables=self.valid_extra_tables,
            mode='add', defaults=defaults
        )

        self.update_modal = component_utils.create_modal(
            self.table, self.table_name, extra_tables=self.valid_extra_tables,
            mode='update', defaults=defaults
        )

        self.construct_layout()

        if self.app is not None and hasattr(self, 'callbacks'):
            self.callbacks(self.app)

    def construct_layout(
            self,
            main_display_table=None,
            add_modal=None,
            update_modal=None,
    ):

        if main_display_table:
            self.main_display_table = main_display_table
        else:
            self.main_display_table = component_utils.create_display_table(
                self.table, f'{self.table_name}-table',
                height=self.table_height, width=self.table_width,
                data=self.main_table_data)

        if self.valid_extra_tables:

            self.valid_extra_table_fields = [
                t.heading.names for t in self.valid_extra_tables]
            self.valid_extra_table_attrs = [
                t.heading.attributes for t in self.valid_extra_tables]
            self.valid_extra_table_pks = [
                t.heading.primary_key for t in self.valid_extra_tables]
            self.valid_extra_table_names = [
                f'{self.table_name}-{t.__name__.lower()}'
                for t in self.valid_extra_tables]
            self.valid_extra_table_original_names = [
                t.__name__ for t in self.valid_extra_tables]
            self.n_extra_tables = len(self.valid_extra_table_fields)
            self.valid_extra_table_schemas = [
                t.database for t in self.valid_extra_tables]

            self.valid_extra_table_is_part = [
                _get_tier(t.full_table_name) == dj.user_tables.Part
                for t in self.valid_extra_tables]
            self.valid_extra_table_master_names = [
                t._master.__name__ if is_part else None
                for t, is_part in zip(self.valid_extra_tables,
                                      self.valid_extra_table_is_part)]

            self.display_extra_tables = []
            for t in self.valid_extra_tables:
                self.display_extra_tables.append(
                    html.Div(
                        [
                            html.H6(f'{t.__name__}'),
                            component_utils.create_display_table(
                                t, f'{self.table_name}-{t.__name__.lower()}-table',
                                excluded_fields=self.primary_key,
                                empty_first=True,
                                height='200px', selectable=False)
                        ]
                    )
                )
                self.display_table = html.Div(
                    [
                        dbc.Row(
                            [
                                html.Div(
                                    [
                                        html.H6(f'{self.table.__name__}'),
                                        self.main_display_table
                                    ],
                                ),
                                dbc.Col(self.display_extra_tables),
                            ],
                        )
                    ]
                )
        else:
            self.display_table = html.Div(
                [
                    html.H6(f'{self.table.__name__}'),
                    self.main_display_table
                ]
            )

        if add_modal:
            self.add_modal = add_modal

        if update_modal:
            self.update_modal = update_modal

        self.layout = html.Div(
            html.Div(
                className="row app-body",
                children=[
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Div(
                                                self.add_button,
                                                style={'display': 'inline-block'}),

                                            html.Div(
                                                self.delete_button,
                                                style={'display': 'inline-block'}),

                                            html.Div(
                                                self.update_button,
                                                style={'display': 'inline-block'})
                                        ],
                                    ),
                                    self.delete_message_box,
                                    self.filter_collection_layout,
                                ],
                                style={'marginLeft': '-2.5em', 'display': 'inline-block'}
                            ),

                            html.Div(
                                [
                                    self.display_table
                                ],
                                style={'marginRight': '2em',
                                       'marginLeft': '-2.5em',
                                       'display': 'inline-block'})

                        ]
                    ),

                    # confirmation dialogue
                    html.Div(self.delete_confirm),
                    # modals
                    self.update_modal,
                    self.add_modal
                ]

            )
        )

    def get_pk(self, entry):
        return {
            k: v
            for k, v in callback_utils.clean_single_gui_record(
                entry, self.attrs).items()
            if k in self.primary_key}

    def get_toggle_variables(self, mode):

        toggle_outputs = \
            [
                Output(f'{mode}-{self.table_name}-modal', 'is_open'),
                Output(f'{mode}-{self.table_name}-table', 'data'),
            ]
        toggle_inputs = \
            [
                Input(f'{mode}-{self.table_name}-button', 'n_clicks'),
                Input(f'{mode}-{self.table_name}-close', 'n_clicks'),
            ]
        toggle_states = \
            [
                State(f'{mode}-{self.table_name}-modal', 'is_open'),
                State(f'{self.table_name}-table', 'data'),
                State(f'{self.table_name}-table', 'selected_rows'),
                State(f'{mode}-{self.table_name}-table', 'data'),
            ]

        if self.valid_extra_tables:

            toggle_outputs += [
                Output(f'{mode}-{name}-table', 'data')
                for name in self.valid_extra_table_names
            ]
            toggle_inputs += [
                Input(f'{mode}-{name}-add-row-button', 'n_clicks')
                for name in self.valid_extra_table_names
            ]

            toggle_states += \
                [
                    State(f'{name}-table', 'data')
                    for name in self.valid_extra_table_names
                ] + \
                [
                    State(f'{mode}-{name}-table', 'data')
                    for name in self.valid_extra_table_names
                ]

        return toggle_outputs, toggle_inputs, toggle_states

    def callbacks(self, app):

        @app.callback(
            [
                Output(f'delete-{self.table_name}-button', 'disabled'),
                Output(f'update-{self.table_name}-button', 'disabled')
            ],
            [
                Input(f'{self.table_name}-table', 'selected_rows')
            ])
        def set_button_enabled_state(selected_rows):
            if selected_rows:
                disabled = False
            else:
                disabled = True
            return disabled, disabled

        @app.callback(
            Output(f'delete-{self.table_name}-confirm', 'displayed'),
            [Input(f'delete-{self.table_name}-button', 'n_clicks')])
        def display_delete_confirm(n_clicks):
            if n_clicks:
                return True
            return False

        # ---------------------- callback update table data ------------------------
        if not self.valid_extra_tables:
            update_table_data_outputs = [
                Output(f'{self.table_name}-table', 'data'),
                Output(f'delete-{self.table_name}-message-box', 'value')
            ]
        else:
            update_table_data_outputs = \
                [Output(f'{self.table_name}-table', 'data')] + \
                [Output(f'{self.table_name}-{t.__name__.lower()}-table', 'data')
                 for t in self.valid_extra_tables] + \
                [Output(f'delete-{self.table_name}-message-box', 'value')]

        update_table_data_inputs = [
            Input(f'add-{self.table_name}-close', 'n_clicks'),
            Input(f'delete-{self.table_name}-confirm', 'submit_n_clicks'),
            Input(f'update-{self.table_name}-close', 'n_clicks'),
            Input(f'{self.table_name}-table', 'selected_rows')
        ]
        if self.filter_collection.filters:
            update_table_data_inputs += [
                Input(f.filter_id, 'value') for f in self.filter_collection.filters.values()
            ]

        @app.callback(
            update_table_data_outputs,
            update_table_data_inputs,
            [
                State(f'{self.table_name}-table', 'data'),
            ]
        )
        def update_table_data(*args):
            n_clicks_add_close, n_clicks_delete, n_clicks_update_close, selected_rows = args[0:4]
            data = args[-1]
            filter_values = args[4:-1]
            if hasattr(self, 'filters') and len(filter_values) != len(self.filters.values()):
                raise ValueError('Number of filter value inputs does not match the number of filters')

            delete_message = f'Delete {self.table.__name__} record message:\n'
            ctx = dash.callback_context
            triggered_component = ctx.triggered[0]['prop_id'].split('.')[0]

            if triggered_component == f'delete-{self.table_name}-confirm' and \
                    selected_rows:
                pk = self.get_pk(data[selected_rows[0]])
                try:
                    if _get_tier(self.table.full_table_name) == dj.user_tables.Part:
                        (self.table & pk).delete(force=True)
                    else:
                        (self.table & pk).delete()
                    delete_message = delete_message + \
                        f'Successfully deleted record {pk}!'
                except Exception as e:
                    delete_message = delete_message + \
                        f'Error in deleting record {pk}: {str(e)}.'
                data = self.table.fetch(as_dict=True)
                self.main_table_data = data
            elif triggered_component in (f'add-{self.table_name}-close',
                                         f'update-{self.table_name}-close'):
                data = self.table.fetch(as_dict=True)
                self.main_table_data = data
            elif 'filter' in triggered_component:
                f = self.filter_collection.filters[triggered_component]
                f.update_query(filter_values)
                query = self.filter_collection.apply_filters(self.table)
                data = query.fetch(as_dict=True)

            if self.valid_extra_tables:
                if selected_rows and selected_rows[0] < len(data):
                    pk = self.get_pk(data[selected_rows[0]])
                    extra_table_data = [
                        (t & pk).fetch(as_dict=True)
                        for t, fields in zip(
                            self.valid_extra_tables,
                            self.valid_extra_table_fields)
                    ]
                else:
                    extra_table_data = [
                        [{f: '' for f in fields}]
                        for t, fields in zip(
                            self.valid_extra_tables,
                            self.valid_extra_table_fields)
                    ]
            if self.valid_extra_tables:
                return tuple([data] + extra_table_data + [delete_message])
            else:
                return tuple([data] + [delete_message])

        def toggle_modal(*args, mode='add'):

            if len(args) == 6:
                (n_open, n_close,
                 is_open, data, selected_rows,
                 modal_data) = args

            elif len(args) > 6 and \
                    len(args) - 6 == 3*len(self.valid_extra_tables):

                (n_open, n_close) = args[:2]
                idx_end = 2 + self.n_extra_tables
                n_add_row_extra_tables = args[2:idx_end]

                is_open, data, selected_rows = args[idx_end:idx_end+3]
                modal_data = args[idx_end+3]
                idx_start = idx_end + 4
                idx_end = idx_start + self.n_extra_tables
                data_extra_tables = list(args[idx_start:idx_end])
                modal_data_extra_tables = list(args[idx_end:])
            else:
                raise ValueError('Invalid callback input arguments.')

            ctx = dash.callback_context
            triggered_component = ctx.triggered[0]['prop_id'].split('.')[0]

            if self.valid_extra_tables:
                add_row_buttons = [
                    f'{mode}-{name}-add-row-button'
                    for name in self.valid_extra_table_names]

            if triggered_component == f'{mode}-{self.table_name}-button':
                if selected_rows:
                    modal_data = [data[selected_rows[0]]]
                    if self.defaults:
                        modal_data = [{k: self.defaults[k]
                                       if k in self.defaults.keys()
                                       else v
                                       for k, v in modal_data[0].items()}]
                    if self.valid_extra_tables:
                        modal_data_extra_tables = data_extra_tables
                else:
                    if mode == 'add':
                        modal_data = [{k: self.defaults[k] if k in self.defaults.keys()
                                       else ''
                                       for k in self.field_names}]
                        if self.valid_extra_tables:
                            modal_data_extra_tables = [
                                [{k: '' for k in fields
                                  if k not in self.primary_key}]
                                for fields in self.valid_extra_table_fields
                            ]
                    elif mode == 'update':
                        raise ValueError(
                            'Update Modal open without a particular row selected')

                modal_open = not is_open if n_open or n_close else is_open

            elif self.valid_extra_tables and \
                    triggered_component in add_row_buttons:
                table_idx = add_row_buttons.index(triggered_component)
                modal_data_extra_tables[table_idx] += \
                    [{k: '' for k in self.valid_extra_table_fields[table_idx]
                     if k not in self.primary_key}]

                modal_open = is_open

            elif triggered_component == f'{mode}-{self.table_name}-close':
                modal_open = not is_open if n_open or n_close else is_open

            elif 'filter' in triggered_component:
                pass

            else:
                modal_open = is_open

            if self.valid_extra_tables:
                return tuple([modal_open] + [modal_data] + modal_data_extra_tables)
            else:
                return tuple([modal_open] + [modal_data])

        @app.callback(
            *self.get_toggle_variables(mode='add')
        )
        def toggle_add_modal(*args):
            return toggle_modal(*args, mode='add')

        @app.callback(
            *self.get_toggle_variables(mode='update')
        )
        def toggle_update_modal(*args):
            return toggle_modal(*args, mode='update')

        if self.valid_extra_tables:
            add_record_states = \
                [
                    State(f'add-{self.table_name}-table', 'data')
                ] + \
                [
                    State(f'add-{name}-table', 'data')
                    for name in self.valid_extra_table_names
                ] + \
                [
                    State(f'add-{self.table_name}-message', 'value')
                ]
        else:
            add_record_states = \
                [
                    State(f'add-{self.table_name}-table', 'data'),
                    State(f'add-{self.table_name}-message', 'value')
                ]

        @app.callback(
            Output(f'add-{self.table_name}-message', 'value'),
            [
                Input(f'add-{self.table_name}-confirm', 'n_clicks'),
                Input(f'add-{self.table_name}-close', 'n_clicks')
            ],
            add_record_states
        )
        def add_record(*args):

            if len(args) == 4:
                (n_clicks_add, n_clicks_close,
                 new_data, add_message) = args
            elif self.valid_extra_table_fields and \
                    len(args) == 4 + len(self.valid_extra_table_fields):
                (n_clicks_add, n_clicks_close, new_data) = args[:3]
                new_data_extra_tables = list(args[3:3+self.n_extra_tables])
                add_message = args[-1]
            else:
                raise ValueError('Invalid callback input arguments for add record.')

            ctx = dash.callback_context
            triggered_component = ctx.triggered[0]['prop_id'].split('.')[0]

            if triggered_component == f'add-{self.table_name}-confirm':

                entry = callback_utils.clean_single_gui_record(
                    new_data[0], self.attrs)

                add_message = 'Add message:'
                pk = self.get_pk(entry)
                try:
                    if (self.table & pk):
                        add_message = add_message + \
                            f'\nWarning: record {pk} exists in database\n'
                    else:
                        self.table.insert1(entry)
                        add_message = add_message + \
                            f'\nSuccessfully inserted into {self.table.__name__}.\n'
                except Exception as e:
                    add_message = add_message + \
                        f'\nError inserting into {self.table_name}: {str(e)}'

                if self.valid_extra_tables:
                    for t, data_t in zip(
                            self.valid_extra_tables,
                            new_data_extra_tables):

                        add_message = callback_utils.insert_part_table(
                            t, pk, data_t, msg=add_message)

            elif triggered_component == f'add-{self.table_name}-close':
                add_message = 'Add message:'

            return add_message

        update_record_states = \
            [
                State(f'update-{self.table_name}-table', 'data'),
            ]
        if self.valid_extra_tables:
            update_record_states += \
            [
                State(f'update-{name}-table', 'data')
                for name in self.valid_extra_table_names
            ]

        @app.callback(
            Output(f'update-{self.table_name}-message', 'value'),
            [
                Input(f'update-{self.table_name}-confirm', 'n_clicks')
            ],
            update_record_states
        )
        def update_record(*args):

            if len(args) == 2:
                (n_clicks, update_data) = args
            elif self.valid_extra_tables and len(args) == 2 + self.n_extra_tables:
                n_clicks, update_data = args[:2]
                update_data_extra_tables = list(args[2:])
            else:
                raise ValueError('Invalid callback input arguments for update record.')

            new = update_data[0]
            pk = {k: v for k, v in new.items() if k in self.primary_key}
            msg = callback_utils.update_table(self.table, new, pk)

            if self.valid_extra_tables:
                for t, data_t in zip(
                        self.valid_extra_tables,
                        update_data_extra_tables):

                    msg = callback_utils.update_part_table(
                        t, pk, data_t, msg)
            return msg

    def refresh_tables(self):

        if not self.refreshed:

            vm = dj.create_virtual_module(
                self.schema_name, self.schema_name)
            if self.table_is_part:
                master_table = getattr(vm, self.master_name)
                self.table = getattr(master_table, self.table_original_name)
            else:
                self.table = getattr(vm, self.table_original_name)

            if self.valid_extra_tables:
                self.valid_extra_tables = []
                for schema_name, table_name, is_part, master_name in zip(
                        self.valid_extra_table_schemas,
                        self.valid_extra_table_original_names,
                        self.valid_extra_table_is_part,
                        self.valid_extra_table_master_names):
                    vm = dj.create_virtual_module(schema_name, schema_name)
                    if is_part:
                        master_table = getattr(vm, master_name)
                        table = getattr(master_table, table_name)
                    else:
                        table = getattr(vm, table_name)

                    self.valid_extra_tables.append(table)
