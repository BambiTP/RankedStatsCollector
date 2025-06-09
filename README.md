# TagPro CTF Statistics Pipeline

This repository contains a Python-based pipeline for fetching, processing, and analyzing Capture the Flag match data from TagPro. It generates detailed player and map statistics, producing CSV, TXT, and Excel outputs for performance analysis.

## Features

- **Fetch New Matches**: Downloads recent match data from tagpro.eu using sitemaps.
- **Process Match Data**: Extracts raw and advanced statistics (e.g., captures, grabs, returns, handoffs) using the `tagpro_eu` library.
- **Aggregate Statistics**: Compiles per-match data into overall and per-map statistics.
- **Derived Metrics**: Computes advanced metrics like captures per minute, win percentage, and returns in base.
- **Formatted Outputs**: Generates CSVs, TXT files, and a formatted Excel workbook with player and map statistics.
- **Error Handling**: Logs failed matches and skips invalid data to ensure robustness.
- **Incremental Processing**: Tracks processed matches to avoid redundant work.

## Prerequisites

- **Python**: Version 3.8 or higher.
- **Dependencies**:
  - `requests`
  - `pandas`
  - `openpyxl`
  - `tagpro-eu`
- **Operating System**: Tested on Linux; should work on Windows with minor path adjustments.
- **Internet Access**: Required to fetch match data from tagpro.eu.

## Installation

1. **Clone the Repository**:

   ```bash
   git clone https://github.com/BambiTP/RankedStatsCollector.git
   cd tagpro-ctf-stats
   ```

2. **Set Up a Virtual Environment** (recommended):

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**:

   ```bash
   pip install requests pandas openpyxl tagpro-eu
   ```

## Usage

1. **Run the Pipeline**: Execute the main script to fetch, process, and analyze match data:

   ```bash
   python3 ctf_statistics.py
   ```

   This will:

   - Check dependencies.
   - Fetch new matches (starting from the ID in `latest_match.txt`).
   - Process matches and generate per-match CSVs in a new `outputs/run_<match_id>` folder.
   - Compile aggregated and combined statistics.
   - Append results to `combinedStatsMaster.csv`.
   - Generate final statistics in a `Stats(n)` folder.

2. **Outputs**:

   - **Per-Run Outputs** (`outputs/run_<match_id>`):
     - `<match_id>.csv`: Per-match player statistics.
     - `AggregatedStatsOutput.csv`: Aggregated player stats.
     - `CombinedStatsOutput.csv`: Per game stats.
     - `failed_matches.txt`: List of failed match IDs (if any).
   - **Final Statistics** (`Stats(n)`):
     - `players_stats_overall.csv`: Overall player statistics.
     - `map_results.csv`: Win rates per map.
     - `stats_<map_name>.csv`: Per-map player statistics.
     - `combined_stats.xlsx`: Formatted Excel workbook with all stats.

3. **Customization**:

   - Modify `stats.py` to add new derived statistics.
   - Adjust filters in `eu_ctf.py` (e.g., `timeLimit == 8`) for different match criteria.
   - Update `latest_match.txt` to reprocess matches from a specific ID.

## Contributing

Contributions are welcome! To contribute:

1. **Fork the Repository** and create a new branch:

   ```bash
   git checkout -b feature/your-feature
   ```

2. **Make Changes** and test thoroughly:

   - Ensure compatibility with Python 3.8+.
   - Test with sample match data if possible.
   - Update documentation for new features.

3. **Submit a Pull Request**:

   - Describe your changes clearly.
   - Include any new dependencies or setup steps.

4. **Ideas for Contributions**:

   - Add parallel processing for match extraction.
   - Implement a configuration file for filters and stats.
   - Create unit tests for key functions.
   - Improve logging with a consistent framework.
   - Add support for new statistics or output formats.

## Known Issues
- **Event Dimension Mismatch**: Some matches fail due to mismatched event data. Failed matches are logged but not retried.
- **Performance**: Processing large numbers of matches can be slow. Consider parallelization for better performance.

## Acknowledgments

- **TagPro Community**: For providing match data and the `tagpro_eu` library.
- **Contributors**: Thanks to all who improve this pipeline.

## Contact

For questions or support, open an issue on GitHub or contact metjr\_ on discord
