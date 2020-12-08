import datetime
import datajoint as dj
import pdb


def clean_single_gui_record(d, attrs, master_key=None):

    if (not master_key and set(d.values()) != {''}) or \
            (master_key and
                set([v for k, v in d.items()
                    if k in (set(d.keys()) - set(master_key.keys()))]) != {''}):

        for k, v in d.items():

            if 'varchar' not in attrs[k].type and v == '':
                d[k] = None

            elif not d[k]:
                continue

            elif attrs[k].type == 'date':
                try:
                    d[k] = datetime.datetime.strptime(v, '%Y-%m-%d').date()
                except ValueError:
                    return f'Invalid date value {v}'

            elif attrs[k].type == 'datetime':
                try:
                    d[k] = datetime.datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    return f'Invalid datetime value {v}'

            elif attrs[k].type == 'timestamp':
                try:
                    d[k] = datetime.datetime.strptime(v, '%Y-%m-%dT%H:%M:%S')
                except ValueError:
                    return f'Invalid timestamp value {v}'

            elif 'int' in attrs[k].type:
                try:
                    d[k] = int(v)
                except ValueError:
                    return f'Invalid int value {v}'

            elif [t for t in ['float', 'double', 'decimal'] if t in attrs[k].type]:
                try:
                    d[k] = float(v)
                except ValueError:
                    return f'Invalid numeric value {v}'

        return d

    else:
        return None


def clean_gui_data(table, data, master_key=None):

    attrs = table.heading.attributes

    clean_data = []
    for d in data:
        clean_d = clean_single_gui_record(d, attrs, master_key=master_key)
        if d:
            clean_data.append(d)

    return clean_data


def update_table(table, new_data, pk=None, msg='Update message:\n'):

    if not pk:
        pks = table.heading.primary_key
        if type(new_data) != dict:
            raise TypeError('new data record has to be a single dictionary.')

        pk = {k: v for k, v in new_data.items() if k in pks}

    dj.conn().connect()
    if not len(table & pk):
        return msg
    else:
        new = clean_single_gui_record(
            new_data, table.heading.attributes)
        if type(new) == str:
            return msg + new + '\n'

        old = (table & pk).fetch1()

        for f in table.heading.secondary_attributes:
            if new[f] != old[f]:
                try:
                    dj.Table._update(table & pk, f, new[f])
                    msg = msg + f'Successfully updated field {f} ' + \
                        f'from {old[f]} to {new[f]}!\n'
                except Exception as e:
                    msg = msg + str(e) + '\n'

    return msg


def update_part_table(part_table, master_key, new_data, msg=''):

    attrs = part_table.heading.attributes
    pks = part_table.heading.primary_key

    # clean up the new data
    new_data = clean_gui_data(part_table, new_data, master_key)

    if type(new_data) == str:
        # return the error message
        return new_data

    old_data = (part_table & master_key).fetch(as_dict=True)

    if new_data == old_data:
        return msg + f'Part table {part_table.__name__} data unchanged.\n'
    else:
        new_data_pk = [
            {k: v for k, v in d.items() if k in pks}
            for d in new_data]
        old_data_pk = [
            {k: v for k, v in d.items() if k in pks}
            for d in old_data]

        # delete non existing entries
        pks_to_be_deleted = [pk for pk in old_data_pk if pk not in new_data_pk]

        if pks_to_be_deleted:
            try:
                (part_table & pks_to_be_deleted).delete(force=True)
                msg = msg + 'Successfully deleted records from part table ' + \
                    f'{part_table.__name__}.\n'
            except Exception as e:
                msg = msg + 'Error deleting part table ' + \
                    f'{part_table.__name__}.: {str(e)}\n'

        # add new records
        new_records = [
            d for pk, d in zip(new_data_pk, new_data)
            if pk not in old_data_pk]

        if new_records:
            try:
                part_table.insert(new_records)
                msg = msg + 'Successfully insert records into part table ' + \
                    f'{part_table.__name__}.\n'
            except Exception as e:
                for r in new_records:
                    try:
                        part_table.insert1(r)
                        msg = msg + 'Error inserting record in part table ' + \
                            f'{part_table.__name__}, {r}: {str(e)}.\n'
                    except Exception as e:
                        msg = msg + 'Error inserting record in part table ' + \
                            f'{part_table.__name__}, {r}: {str(e)}.\n'

        # update existing records
        records_to_be_updated = [
            (pk, d) for pk, d in zip(new_data_pk, new_data)
            if pk in old_data_pk and d not in old_data]

        if records_to_be_updated:
            for pk, new_record in records_to_be_updated:
                old_record = [
                    d for old_pk, d in zip(old_data_pk, old_data)
                    if old_pk == pk][0]

                for (old_k, old_v), (new_k, new_v) in zip(old_record.items(), new_record.items()):

                    if old_k not in pks and old_v != new_v:
                        try:
                            dj.Table._update(part_table & pk, old_k, new_v)
                            msg = msg + 'Successful update in part table ' + \
                                f'{part_table.__name__} record {pk} ' + \
                                f'in field {old_k}: {old_v} -> {new_v}.\n'

                        except Exception as e:
                            mag = msg + 'Error when updating part table ' + \
                                f'{part_table.__name__} record {pk}: {str(e)}.\n'

    return msg
