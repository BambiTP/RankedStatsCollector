import logging
import os
from json import load
from glob import iglob, glob
from os.path import basename, exists, join, splitext
from urllib.request import urlretrieve
from urllib.error import HTTPError
from datetime import datetime
from math import sqrt
import ssl

import pandas as pd
from pandas import DataFrame, read_csv, concat, merge
import numpy as np
from numpy import nan, inf

# Note: numpy.arange is imported in the original code but not used here.

# Disable logging if desired.
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logging.disable(logging.CRITICAL)

# Global list for failed match ids due to Event dimension mismatch.
failed_match_ids = []


############
# NEW: Load Bulk Data
############
def compile_data(file_directory, output_file):
    """
    Compile match CSVs in `file_directory` into one stats CSV+TXT,
    collapsing Player names case-insensitively and picking the
    most-frequent original spelling for the final 'Player' column.
    """
    if not exists(file_directory):
        raise OSError(f"Directory {file_directory!r} does not exist")

    # 1) Read all your per-match CSVs
    df_all = pd.concat(
        (pd.read_csv(f) for f in iglob(join(file_directory, '*.csv'))),
        ignore_index=True
    )

    # 2) Keep the original name, and make a casefold key
    df_all['Player_orig'] = df_all['Player']
    df_all['Player_key']  = df_all['Player_orig'].str.casefold()

    # 3) Figure out which columns are numeric so we sum those
    numeric_cols = df_all.select_dtypes(include=[np.number]).columns.tolist()

    # 4) Build an agg dict: sum all numeric stats, and for Player_orig take the mode
    agg_dict = {col: 'sum' for col in numeric_cols}
    agg_dict['Player_orig'] = lambda names: names.mode()[0]

    # 5) Group by the casefold key
    df = (
        df_all
        .groupby('Player_key', as_index=False)
        .agg(agg_dict)
        # rename our representative spelling back to 'Player'
        .rename(columns={'Player_orig': 'Player'})
    )

    # 6) Drop the helper key
    df.drop(columns=['Player_key'], inplace=True)

    # 7) Re-order so Player is first
    other_cols = [c for c in df.columns if c != 'Player']
    df = df[['Player'] + other_cols]

    # 8) Recompute your cumulative derivatives
    df = cumulative_derivative_statistics(df)

    # 9) Write out CSV + TXT
    df.to_csv(output_file, index=False)
    with open(output_file.replace('.csv', '.txt'), 'w') as f:
        f.write(df.to_string(index=False))


def load_bulk_matches(bulk_matches_file):
    """
    Loads the bulk JSON file containing many matches.
    The file is expected to have a dictionary keyed by match id.
    """
    with open(bulk_matches_file, 'r', encoding='utf-8') as f:
        bulk_match_data = load(f)
    return bulk_match_data


def load_bulk_maps(bulk_maps_file):
    """
    Loads the bulk JSON file containing map data.
    It is expected that this file is a dictionary keyed by map ids.
    """
    with open(bulk_maps_file, 'r', encoding='utf-8') as f:
        bulk_map_data = load(f)
    return bulk_map_data


############
# UPDATED: read_match_from_bulk using tagpro-eu decoding
############

def read_match_from_bulk(match_id, bulk_match_data, bulk_map_data):
    """
    Reads a match using its id from bulk_match_data and attaches a decoded map
    using the tagpro-eu library. The bulk maps are stored in a separate JSON file,
    and the match data references a mapId which is used to find the corresponding map.

    Only matches with timeLimit == 8 and an empty group are processed.
    If the match does not meet these criteria, a ValueError is raised.
    """
    # Retrieve the raw match JSON data.
    match_data = bulk_match_data.get(str(match_id))
    if match_data is None:
        raise ValueError(f"Match data for id {match_id} not found in bulk file.")

    # Filter out matches that do not have timeLimit 8 or an empty group.
    if match_data.get("timeLimit") != 8 or match_data.get("group", "") != "":
        raise ValueError(f"Match {match_id} skipped: does not meet criteria (timeLimit 8 and empty group required).")

    # Create a Match object using the tagpro_eu library.
    from tagpro_eu.match import Match
    match_obj = Match(match_data)

    # Save the map id for further lookup.
    match_obj.mapId = match_data.get("mapId")

    # Lookup the raw map JSON object using the map id.
    map_data = bulk_map_data.get(str(match_obj.mapId))
    if not map_data:
        raise ValueError(f"Map with id {match_obj.mapId} not found in bulk maps data.")

    # Use tagpro-eu's built-in Map decoding.
    from tagpro_eu.map import Map as TagMap
    match_obj.map = TagMap(map_data)

    return match_obj


############
# UPDATED: extract_match_data with error handling for event dimension mismatch
############

def extract_match_data(match_id, bulk_match_data, bulk_map_data, current_output_directory):
    try:
        match = read_match_from_bulk(match_id, bulk_match_data, bulk_map_data)
    except ValueError as e:
        logging.error(e)
        return None  # Skip processing for this match.

    df = DataFrame()

    timeline = match.create_timeline()
    join_events = [k for k in timeline if 'Join team' in k[1]]
    player_team_dict = {join_event[2].name: join_event[1].split()[-1] for join_event in join_events}

    df['Player'] = [player.name for player in match.players]
    df['Team'] = df['Player'].apply(lambda x: player_team_dict.get(x))

    time_statistics = ['time', 'hold', 'prevent', 'block', 'button']
    desired_statistics = ['time', 'cap_diff', 'captures', 'grabs', 'hold', 'drops', 'pops',
                          'returns', 'tags', 'prevent', 'pups_total', 'block', 'button']

    for field in desired_statistics:
        if field in time_statistics:
            df[field] = [getattr(getattr(player.stats, field), 'seconds') for player in match.players]
        else:
            df[field] = [getattr(player.stats, field) for player in match.players]

    df.rename(columns={
        'time': 'Time', 'cap_diff': 'CD', 'captures': 'Captures', 'grabs': 'Grabs', 'hold': 'Hold',
        'drops': 'Drops', 'pops': 'Pops', 'returns': 'Returns', 'tags': 'Tags', 'prevent': 'Prevent',
        'pups_total': 'Pups', 'block': 'Block', 'button': 'Button'
    }, inplace=True)
    df = individual_game_derivative_statistics(df)

    df = df[['Player', 'Team', 'Minutes', 'CD', 'Captures', 'Grabs', 'Hold', 'Drops',
             'Pops', 'Returns', 'Tags', 'Prevent', 'Pups', 'Pups Available',
             'Block', 'Button', 'Support', 'Hold Against', 'K/D', 'Pup %', 'Score %',
             'NDPops', 'NRTags', 'KF', 'Hold/Grab', 'Prevent/Return', 'Prevent/Hold Against']]

    try:
        df_advanced = advanced_statistics(match_id, match)
        df = merge(df, df_advanced, on=['Player'])
        df = advanced_derivative_statistics(df)
    except ValueError as e:
        # Check if the error is due to event dimension mismatch.
        if "Event dimension mismatch" in str(e):
            logging.error(e)
            # Prepare the output file path.
            output_file = f"{match_id}.csv"
            full_path = join(current_output_directory, output_file)
            # If the CSV file was written, delete it.
            if exists(full_path):
                os.remove(full_path)
            # Record the failed match id.
            global failed_match_ids
            failed_match_ids.append(match_id)
            return None  # Skip this match.
        else:
            raise

    # Write the CSV file if everything processed correctly.
    output_file = f"{match_id}.csv"
    full_path = join(current_output_directory, output_file)
    df.to_csv(full_path, index=False)
    return df


############
# UPDATED: advanced_statistics with tagpro-eu map decoding for flag locations
############

def advanced_statistics(match_id,match):
    timeline = match.create_timeline()
    events = [k for k in timeline if k[1] in ['Grab Opponent flag','Return','Drop Opponent flag','Capture Opponent flag','Grab Temporary flag','Drop Temporary flag','Capture Temporary flag']]

    team_dictionary = {}
    join_events = [k for k in timeline if 'Join team' in k[1]]
    for join_event in join_events:
        if (join_event[2].name not in team_dictionary):
            team_dictionary[join_event[2].name] = join_event[1].split()[-1]

    teams = [match.team_blue.name,match.team_red.name]

    for i,event in enumerate(events):
        event = list(event)
        event[0] = to_seconds(str(event[0]))
        event.append(team_dictionary[event[-1].name])

        if (event[1] == 'Grab Temporary flag'):
            event[1] = 'Grab Opponent flag'

        if (event[1] == 'Drop Temporary flag'):
            event[1] = 'Drop Opponent flag'

        if (event[1] == 'Capture Temporary flag'):
            event[1] = 'Capture Opponent flag'

        events[i] = event

    events = sorted(events,key = lambda x: (x[0],x[1]))

    start_events_Blue = []
    start_events_Red = []
    end_events_Blue = []
    end_events_Red = []

    for event in events:
        if (event[1] == 'Grab Opponent flag' and event[-1] == teams[0]):
            start_events_Blue.append(event)

        elif (event[1] == 'Grab Opponent flag' and event[-1] == teams[-1]):
            start_events_Red.append(event)

        if (event[1] in ['Drop Opponent flag','Capture Opponent flag'] and event[-1] == teams[0]):
            end_events_Blue.append(event)

        elif (event[1] in ['Drop Opponent flag','Capture Opponent flag'] and event[-1] == teams[-1]):
            end_events_Red.append(event)

        if (event[1] == 'Return' and event[-1] == teams[-1]):
            if (end_events_Blue[-1][1] == 'Drop Opponent flag' and end_events_Blue[-1][0] == event[0]):
                end_events_Blue.pop()
                end_events_Blue.append(event)
            else:
                end_events_Blue.append(event)

        elif (event[1] == 'Return' and event[-1] == teams[0]):
            if (end_events_Red[-1][1] == 'Drop Opponent flag' and end_events_Red[-1][0] == event[0]):
                end_events_Red.pop()
                end_events_Red.append(event)

            else:
                end_events_Red.append(event)

    to_delete_Blue = []
    for i in range(1,len(end_events_Blue)):
        if (round(end_events_Blue[i][0] - end_events_Blue[i-1][0],2) < 0.25):
            if (end_events_Blue[i-1][1] == 'Drop Opponent flag'):
                to_delete_Blue.append(i-1)

            elif (end_events_Blue[i][1] == 'Drop Opponent flag'):
                to_delete_Blue.append(i)

            else:
                to_delete_Blue.append(i)

    to_delete_Red = []
    for i in range(1,len(end_events_Red)):
        if (round(end_events_Red[i][0] - end_events_Red[i-1][0],2) < 0.25):
            if (end_events_Red[i-1][1] == 'Drop Opponent flag'):
                to_delete_Red.append(i-1)

            elif (end_events_Red[i][1] == 'Drop Opponent flag'):
                to_delete_Red.append(i)

            else:
                to_delete_Red.append(i)

    end_events_Blue = [v for i,v in enumerate(end_events_Blue) if i not in to_delete_Blue]
    end_events_Red = [v for i,v in enumerate(end_events_Red) if i not in to_delete_Red]

    if (len(end_events_Blue) < len(start_events_Blue)):
        end_events_Blue.append([match.duration.seconds,'Game ends',None,None])

    if (len(end_events_Red) < len(start_events_Red)):
        end_events_Red.append([match.duration.seconds,'Game ends',None,None])

    if (len(end_events_Blue) != len(start_events_Blue) or len(end_events_Red) != len(start_events_Red)):
        raise ValueError('Event dimension mismatch while processing EU {}'.format(match_id))

    tile_dimension = 40.0
    flag_locations = []
    tiles = match.map.tiles

    for i in range(0,len(tiles)):
        for j in range(0,len(tiles[i])):
            if (tiles[i][j].value == 40):
                x_location_Blue = (j + 1.0) * tile_dimension - (0.5 * tile_dimension)
                y_location_Blue = (i + 1.0) * tile_dimension - (0.5 * tile_dimension)

            elif (tiles[i][j].value == 30):
                x_location_Red = (j + 1.0) * tile_dimension - (0.5 * tile_dimension)
                y_location_Red = (i + 1.0) * tile_dimension - (0.5 * tile_dimension)

    flag_locations.append((x_location_Blue,y_location_Blue))
    flag_locations.append((x_location_Red,y_location_Red))

    splat_events = match.splats

    splats = []
    for s in splat_events:
        splats.append([to_seconds(str(s.time)),(s.x,s.y),s.player,s.team.name])

    df = DataFrame()
    df['Player'] = team_dictionary.keys()
    columns = ['Long Holds','Flaccids','Handoffs','Good Handoffs','Captures off Handoffs','Quick Returns','Key Returns','Returns in Base']
    for column in columns:
        df[column] = 0

    for i in range(0,len(start_events_Blue)):
        if (round(abs(end_events_Blue[i][0] - start_events_Blue[i][0]),2) >= 20.0):
            df.loc[df['Player'] == start_events_Blue[i][-2].name,'Long Holds'] += 1

        if (round(abs(end_events_Blue[i][0] - start_events_Blue[i][0]),2) < 2.0):
            df.loc[df['Player'] == start_events_Blue[i][-2].name,'Flaccids'] += 1

            if (end_events_Blue[i][1] == 'Return'):
                df.loc[df['Player'] == end_events_Blue[i][-2].name,'Quick Returns'] += 1

        if (i > 0):
            if (round(abs(end_events_Blue[i-1][0] - start_events_Blue[i-1][0]),2) < 3.0 and round(abs(start_events_Blue[i][0] - end_events_Blue[i-1][0]),2) < 2.0):
                df.loc[df['Player'] == start_events_Blue[i-1][-2].name,'Handoffs'] += 1

                if (round(abs(end_events_Blue[i][0] - start_events_Blue[i][0]),2) >= 5.0):
                    df.loc[df['Player'] == start_events_Blue[i-1][-2].name,'Good Handoffs'] += 1

                if (end_events_Blue[i][1] == 'Capture Opponent flag'):
                    df.loc[df['Player'] == end_events_Blue[i][-2].name,'Captures off Handoffs'] += 1

        if (end_events_Blue[i][1] == 'Capture Opponent flag'):
            viable_return_events = [x for x in end_events_Red if x[1] == 'Return' and x[0] <= end_events_Blue[i][0]]

            if (viable_return_events):
                index = min(range(0,len(viable_return_events)),key = lambda j: round(abs(viable_return_events[j][0] - end_events_Blue[i][0]),2))

                if (round(abs(end_events_Blue[i][0] - viable_return_events[index][0]),2) < 3):
                    df.loc[df['Player'] == viable_return_events[index][-2].name,'Key Returns'] += 1

        if (end_events_Blue[i][1] == 'Return'):
            viable_splats = [s for s in splats if s[0] == end_events_Blue[i][0] and s[-1] == start_events_Blue[i][-1]]

            if (viable_splats):
                distance_to_enemy_flag = sqrt((flag_locations[-1][0] - viable_splats[0][1][0])**2 + (flag_locations[-1][1] - viable_splats[0][1][1])**2)

                if (distance_to_enemy_flag <= 5.5 * tile_dimension):
                    df.loc[df['Player'] == end_events_Blue[i][-2].name,'Returns in Base'] += 1

    for i in range(0,len(start_events_Red)):
        if (round(abs(end_events_Red[i][0] - start_events_Red[i][0]),2) >= 20.0):
            df.loc[df['Player'] == start_events_Red[i][-2].name,'Long Holds'] += 1

        if (round(abs(end_events_Red[i][0] - start_events_Red[i][0]),2) < 2.0):
            df.loc[df['Player'] == start_events_Red[i][-2].name,'Flaccids'] += 1

            if (end_events_Red[i][1] == 'Return'):
                df.loc[df['Player'] == end_events_Red[i][-2].name,'Quick Returns'] += 1

        if (i > 0):
            if (round(abs(end_events_Red[i-1][0] - start_events_Red[i-1][0]),2) < 3.0 and round(abs(start_events_Red[i][0] - end_events_Red[i-1][0]),2) < 2.0):
                df.loc[df['Player'] == start_events_Red[i-1][-2].name,'Handoffs'] += 1

                if (round(abs(end_events_Red[i][0] - start_events_Red[i][0]),2) >= 5.0):
                    df.loc[df['Player'] == start_events_Red[i-1][-2].name,'Good Handoffs'] += 1

                if (end_events_Red[i][1] == 'Capture Opponent flag'):
                    df.loc[df['Player'] == end_events_Red[i][-2].name,'Captures off Handoffs'] += 1

        if (end_events_Red[i][1] == 'Capture Opponent flag'):
            viable_return_events = [x for x in end_events_Blue if x[1] == 'Return' and x[0] <= end_events_Red[i][0]]

            if (viable_return_events):
                index = min(range(0,len(viable_return_events)),key = lambda j: round(abs(viable_return_events[j][0] - end_events_Red[i][0]),2))

                if (round(abs(end_events_Red[i][0] - viable_return_events[index][0]),2) < 3):
                    df.loc[df['Player'] == viable_return_events[index][-2].name,'Key Returns'] += 1

        if (end_events_Red[i][1] == 'Return'):
            viable_splats = [s for s in splats if s[0] == end_events_Red[i][0] and s[-1] == start_events_Red[i][-1]]

            if (viable_splats):
                distance_to_enemy_flag = sqrt((flag_locations[0][0] - viable_splats[0][1][0])**2 + (flag_locations[0][1] - viable_splats[0][1][1])**2)

                if (distance_to_enemy_flag <= 5.5 * tile_dimension):
                    df.loc[df['Player'] == end_events_Red[i][-2].name,'Returns in Base'] += 1

    return df


def create_new_stats_folder(base_output_directory):
    i = 1
    while True:
        new_folder = join(base_output_directory, f"Stats({i})")
        if not exists(new_folder):
            os.makedirs(new_folder)
            return new_folder
        i += 1


def combine_stats_csv(current_output_directory, aggregated_output_file, combined_output_file, bulk_match_data, bulk_map_data):
    # Locate all CSV files in the current_output_directory
    csv_files = glob(join(current_output_directory, "*.csv"))
    filter_filename = basename(aggregated_output_file)
    csv_files = [f for f in csv_files if basename(f) != filter_filename]
    csv_files.sort()

    dataframes = []
    for csv_file in csv_files:
        try:
            # Extract match_id from the filename.
            filename = basename(csv_file)
            match_id = filename.split('.')[0]

            # Read CSV into DataFrame.
            df = pd.read_csv(csv_file)
            # Retrieve the match object from the bulk data to extract the map id and then lookup in bulk_map_data.
            # This will automatically skip matches which do not meet the criteria.
            match_obj = read_match_from_bulk(match_id, bulk_match_data, bulk_map_data)
            map_id = str(match_obj.mapId)
            # Assume bulk_map_data[map_id] returns a dictionary with a 'name' key.
            map_name = bulk_map_data.get(map_id, {}).get("name", "Unknown Map")
            df['matchId'] = match_id
            df['mapName'] = map_name
            dataframes.append(df)
        except Exception as e:
            logging.error(f"Skipping file {csv_file} due to error: {e}")

    if dataframes:
        combined_df = pd.concat(dataframes, ignore_index=True)
    else:
        combined_df = pd.DataFrame()

    combined_df.to_csv(combined_output_file, index=False)

    combined_basename = basename(combined_output_file)
    base_name, _ = splitext(combined_basename)
    output_txt_file = join(current_output_directory, base_name + '.txt')

    col_widths = {}
    for col in combined_df.columns:
        header_width = len(str(col))
        if not combined_df.empty:
            max_data_width = combined_df[col].astype(str).map(len).max()
        else:
            max_data_width = 0
        col_widths[col] = max(header_width, max_data_width)

    with open(output_txt_file, 'w', encoding='utf-8') as f:
        header_line = "  ".join(str(col).ljust(col_widths[col]) for col in combined_df.columns)
        f.write(header_line + "\n")
        for _, row in combined_df.iterrows():
            line_parts = []
            for col in combined_df.columns:
                cell_str = str(row[col])
                if pd.api.types.is_numeric_dtype(combined_df[col]):
                    cell_str = cell_str.rjust(col_widths[col])
                else:
                    cell_str = cell_str.ljust(col_widths[col])
                line_parts.append(cell_str)
            line = "  ".join(line_parts)
            f.write(line + "\n")


def individual_game_derivative_statistics(df):
    df['Minutes'] = round(df['Time'] / 60.0, 1)
    df.drop(columns=['Time'], inplace=True)
    df['Pups Available'] = df['Pups'].sum()
    df['Support'] = (df['Button'] // 5) + ((df['Block'] // 5) * 2)
    df['Hold Against'] = df['Team'].map(lambda x: df['Hold'][df['Team'] != x].sum())
    df['K/D'] = round(df['Tags'] / df['Pops'], 2)
    df['Pup %'] = round((df['Pups'] / df['Pups Available']) * 100.0, 2)
    df['Score %'] = round((df['Captures'] / df['Grabs']) * 100.0, 2)
    df['NDPops'] = df['Pops'] - df['Drops']
    df['NRTags'] = df['Tags'] - df['Returns']
    df['KF'] = df['Grabs'] - (df['Drops'] + df['Captures'])
    df['Hold/Grab'] = round(df['Hold'] / df['Grabs'], 2)
    df['Prevent/Return'] = round(df['Prevent'] / df['Returns'], 2)
    df['Prevent/Hold Against'] = round(df['Prevent'] / df['Hold Against'], 2)
    df.replace([nan, inf], 0, inplace=True)
    return df


def advanced_derivative_statistics(df):
    df['Flaccid %'] = round((df['Flaccids'] / df['Grabs']) * 100.0, 2)
    df['Chain %'] = round((df['Good Handoffs'] / df['Handoffs']) * 100.0, 2)
    df['QR %'] = round((df['Quick Returns'] / df['Returns']) * 100.0, 2)
    df['RIB %'] = round((df['Returns in Base'] / df['Returns']) * 100.0, 2)
    df.replace([nan, inf], 0, inplace=True)
    return df


def cumulative_derivative_statistics(df):
    df['K/D'] = round(df['Tags'] / df['Pops'], 2)
    df['Pup %'] = round((df['Pups'] / df['Pups Available']) * 100.0, 2)
    df['Score %'] = round((df['Captures'] / df['Grabs']) * 100.0, 2)
    df['NDPops'] = df['Pops'] - df['Drops']
    df['NRTags'] = df['Tags'] - df['Returns']
    df['KF'] = df['Grabs'] - (df['Drops'] + df['Captures'])
    df['Hold/Grab'] = round(df['Hold'] / df['Grabs'], 2)
    df['Prevent/Return'] = round(df['Prevent'] / df['Returns'], 2)
    df['Prevent/Hold Against'] = round(df['Prevent'] / df['Hold Against'], 2)
    df['Flaccid %'] = round((df['Flaccids'] / df['Grabs']) * 100.0, 2)
    df['Chain %'] = round((df['Good Handoffs'] / df['Handoffs']) * 100.0, 2)
    df['QR %'] = round((df['Quick Returns'] / df['Returns']) * 100.0, 2)
    df['RIB %'] = round((df['Returns in Base'] / df['Returns']) * 100.0, 2)
    df['CD/Min'] = round(df['CD'] / df['Minutes'], 2)
    df['Captures/Min'] = round(df['Captures'] / df['Minutes'], 2)
    df['Grabs/Min'] = round(df['Grabs'] / df['Minutes'], 2)
    df['Hold/Min'] = round(df['Hold'] / df['Minutes'], 2)
    df['Drops/Min'] = round(df['Drops'] / df['Minutes'], 2)
    df['Pops/Min'] = round(df['Pops'] / df['Minutes'], 2)
    df['Returns/Min'] = round(df['Returns'] / df['Minutes'], 2)
    df['Tags/Min'] = round(df['Tags'] / df['Minutes'], 2)
    df['Prevent/Min'] = round(df['Prevent'] / df['Minutes'], 2)
    df['Pups/Min'] = round(df['Pups'] / df['Minutes'], 2)
    df.replace([nan, inf], 0, inplace=True)
    return df


def name_change(name_map, file_directory):
    for f in iglob(file_directory + '/*.csv', recursive=True):
        df = read_csv(f)
        df['Player'].replace(name_map, inplace=True)
        df.to_csv(f, index=False)


def to_seconds(time_string, format='%M:%S.%f'):
    time_obj = datetime.strptime(time_string, format)
    return (time_obj.minute * 60) + time_obj.second + (time_obj.microsecond / 1000000)
