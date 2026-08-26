"""
UTM Test Summary Report Generator

Generates a comprehensive QMD (Quarto Markdown) report from UTM CSV test files.
Includes stress-strain plots, linear elasticity region identification, and modulus calculations.
"""

import os
import glob
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

# Configuration
PLOT_WIDTH = "100%"  # Width of plots in the report (e.g., "100%", "80%")
PLOT_FORMAT = "svg"  # Plot format: "svg" or "png"
PLOT_DPI = 150  # DPI for PNG plots (ignored for SVG)


@dataclass
class TestData:
    """Container for parsed UTM test data."""
    filename: str
    test_date: str
    duration: float
    data_points: int
    comment: str
    scale: float
    offset: float
    area: float
    gauge_length: float
    max_load: float
    max_stress: float
    max_strain: float
    app_version: str
    df: pd.DataFrame
    # Calculated values
    modulus: float = 0.0
    linear_start_strain: float = 0.0
    linear_end_strain: float = 0.0
    yield_stress: float = 0.0


def parse_csv_header(filepath: str) -> dict:
    """Parse metadata from CSV header comments."""
    metadata = {}

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.startswith('#'):
                break
            line = line[1:].strip()  # Remove # and whitespace

            if line.startswith('Test Date:'):
                metadata['test_date'] = line.split(':', 1)[1].strip()
            elif line.startswith('Duration:'):
                match = re.search(r'([\d.]+)', line)
                metadata['duration'] = float(match.group(1)) if match else 0.0
            elif line.startswith('Data Points:'):
                match = re.search(r'(\d+)', line)
                metadata['data_points'] = int(match.group(1)) if match else 0
            elif line.startswith('Comment:'):
                metadata['comment'] = line.split(':', 1)[1].strip()
            elif line.startswith('Calibration'):
                match = re.search(r'Scale:\s*([-\d.]+).*Offset:\s*([-\d.]+)', line)
                if match:
                    metadata['scale'] = float(match.group(1))
                    metadata['offset'] = float(match.group(2))
            elif line.startswith('Specimen'):
                match = re.search(r'Area:\s*([\d.]+).*Gauge Length:\s*([\d.]+)', line)
                if match:
                    metadata['area'] = float(match.group(1))
                    metadata['gauge_length'] = float(match.group(2))
            elif line.startswith('Max Load:'):
                match = re.search(r'([-\d.]+)', line)
                metadata['max_load'] = float(match.group(1)) if match else 0.0
            elif line.startswith('Max Stress:'):
                match = re.search(r'([-\d.]+)', line)
                metadata['max_stress'] = float(match.group(1)) if match else 0.0
            # "Max DIC Strain:" is the current label; "Max Strain:" is what CSVs written before
            # 2026-08-26 carry — and on those it held MOTOR strain (crosshead travel / gauge),
            # not the DIC measurement. Both are read so old files still parse, but the DIC line
            # wins when a file has both.
            elif line.startswith('Max DIC Strain:'):
                match = re.search(r'([-\d.]+)', line)
                metadata['max_strain'] = float(match.group(1)) if match else 0.0
            elif line.startswith('Max Strain:') and 'max_strain' not in metadata:
                match = re.search(r'([-\d.]+)', line)
                metadata['max_strain'] = float(match.group(1)) if match else 0.0
                metadata['max_strain_is_motor'] = True
            elif line.startswith('Max Motor Strain:'):
                match = re.search(r'([-\d.]+)', line)
                metadata['motor_strain'] = float(match.group(1)) if match else 0.0
            elif line.startswith('App Version:'):
                metadata['app_version'] = line.split(':', 1)[1].strip()

    return metadata


def load_test_data(filepath: str) -> TestData:
    """Load and parse a UTM CSV test file."""
    metadata = parse_csv_header(filepath)

    # Read data, skipping comment lines
    df = pd.read_csv(filepath, comment='#')

    return TestData(
        filename=os.path.basename(filepath),
        test_date=metadata.get('test_date', 'Unknown'),
        duration=metadata.get('duration', 0.0),
        data_points=metadata.get('data_points', len(df)),
        comment=metadata.get('comment', ''),
        scale=metadata.get('scale', -0.0065),
        offset=metadata.get('offset', -24.5185),
        area=metadata.get('area', 80.0),
        gauge_length=metadata.get('gauge_length', 80.0),
        max_load=metadata.get('max_load', 0.0),
        max_stress=metadata.get('max_stress', 0.0),
        max_strain=metadata.get('max_strain', 0.0),
        app_version=metadata.get('app_version', 'Unknown'),
        df=df
    )


def find_linear_region(strain: np.ndarray, stress: np.ndarray,
                       min_strain: float = 0.02,
                       yield_drop_threshold: float = 0.7,
                       window_size: int = 20) -> tuple:
    """
    Find the linear elastic region by detecting where plasticity begins.

    Method:
    1. Start at min_strain (default 0.02) to skip the toe region
    2. Calculate rolling tangent modulus (local slope)
    3. Find maximum slope in the elastic region
    4. Identify yield point where slope drops to yield_drop_threshold of max
    5. Fit linear region from min_strain to yield point

    Args:
        strain: Strain values
        stress: Stress values
        min_strain: Minimum strain to start analysis (skip toe region)
        yield_drop_threshold: Fraction of max slope that defines yield (0.7 = 70%)
        window_size: Window size for rolling slope calculation

    Returns:
        (start_idx, yield_idx, modulus, yield_strain)
    """
    n = len(strain)
    if n < window_size * 2:
        return 0, n-1, 0.0, 0.0

    # Find index where strain >= min_strain
    start_idx = np.searchsorted(strain, min_strain)
    if start_idx >= n - window_size:
        start_idx = max(0, n // 10)  # Fallback to 10% of data

    # Calculate rolling tangent modulus (local slope)
    half_window = window_size // 2
    tangent_modulus = np.zeros(n)

    for i in range(half_window, n - half_window):
        x_window = strain[i - half_window:i + half_window]
        y_window = stress[i - half_window:i + half_window]

        # Only calculate if there's enough variation in x
        if np.std(x_window) > 1e-10:
            slope, _, _, _, _ = stats.linregress(x_window, y_window)
            tangent_modulus[i] = max(0, slope)  # Only positive slopes

    # Find maximum tangent modulus in the region after start_idx
    # Look in the first 60% of the curve (elastic region should be there)
    search_end = min(n - half_window, int(n * 0.6))
    search_region = tangent_modulus[start_idx:search_end]

    if len(search_region) == 0 or np.max(search_region) == 0:
        # Fallback: simple linear fit on first 20%
        end_idx = min(int(n * 0.2), n - 1)
        if end_idx > start_idx + 5:
            slope, _, _, _, _ = stats.linregress(strain[start_idx:end_idx], stress[start_idx:end_idx])
            return start_idx, end_idx, max(0, slope), strain[end_idx]
        return 0, n-1, 0.0, 0.0

    max_modulus = np.max(search_region)
    max_modulus_idx = start_idx + np.argmax(search_region)

    # Find yield point: where tangent modulus drops below threshold of max
    yield_threshold = max_modulus * yield_drop_threshold
    yield_idx = None

    # Search from max modulus point forward
    for i in range(max_modulus_idx, search_end):
        if tangent_modulus[i] < yield_threshold:
            yield_idx = i
            break

    # If no clear yield point found, use a reasonable default
    if yield_idx is None:
        yield_idx = search_end

    # Ensure we have enough points for regression
    if yield_idx <= start_idx + 5:
        yield_idx = min(start_idx + window_size, search_end)

    # Calculate modulus from the identified linear region
    x_linear = strain[start_idx:yield_idx]
    y_linear = stress[start_idx:yield_idx]

    if len(x_linear) > 2 and np.std(x_linear) > 1e-10:
        modulus, intercept, r_value, _, _ = stats.linregress(x_linear, y_linear)
        modulus = max(0, modulus)
    else:
        modulus = max_modulus

    yield_strain = strain[yield_idx] if yield_idx < n else strain[-1]

    return start_idx, yield_idx, modulus, yield_strain


def calculate_modulus(test: TestData) -> TestData:
    """Calculate modulus of elasticity and identify yield point."""
    strain = test.df['Strain'].values
    stress = test.df['Stress_MPa'].values

    # Filter out any NaN values
    mask = ~(np.isnan(strain) | np.isnan(stress))
    strain = strain[mask]
    stress = stress[mask]

    if len(strain) < 40:
        return test

    start_idx, yield_idx, modulus, yield_strain = find_linear_region(strain, stress)

    test.modulus = modulus  # MPa (since stress is in MPa and strain is dimensionless)
    test.linear_start_strain = strain[start_idx]
    test.linear_end_strain = yield_strain

    # Calculate yield stress (stress at yield point)
    if yield_idx < len(stress):
        test.yield_stress = stress[yield_idx]

    return test


def save_plot(fig, filepath: str):
    """Save plot in configured format."""
    if PLOT_FORMAT == "svg":
        fig.savefig(filepath, format='svg', bbox_inches='tight')
    else:
        fig.savefig(filepath, dpi=PLOT_DPI, bbox_inches='tight')


def get_plot_extension() -> str:
    """Get file extension for plots."""
    return f".{PLOT_FORMAT}"


def create_stress_strain_plot(test: TestData, output_dir: str,
                              xlim: tuple = None, ylim: tuple = None) -> str:
    """Create a stress-strain plot for a single test."""
    fig, ax = plt.subplots(figsize=(10, 6))

    strain = test.df['Strain'].values
    stress = test.df['Stress_MPa'].values

    # Plot main curve
    ax.plot(strain, stress, 'b-', linewidth=1, label='Stress-Strain Curve')

    # Highlight linear region if found
    if test.modulus > 0:
        mask = (strain >= test.linear_start_strain) & (strain <= test.linear_end_strain)
        linear_strain = strain[mask]
        linear_stress = stress[mask]

        if len(linear_strain) > 0:
            # Plot linear region
            ax.plot(linear_strain, linear_stress, 'g-', linewidth=2,
                    label=f'Linear Region (E = {test.modulus:.0f} MPa)')

            # Plot fitted line extended slightly
            x_fit = np.linspace(0, test.linear_end_strain * 1.2, 100)
            y_fit = test.modulus * x_fit
            ax.plot(x_fit, y_fit, 'r--', linewidth=1, alpha=0.7, label='Linear Fit')

    # Mark max stress point
    max_idx = np.argmax(np.abs(stress))
    ax.plot(strain[max_idx], stress[max_idx], 'ro', markersize=8,
            label=f'Max: {test.max_stress:.1f} MPa @ {test.max_strain:.4f}')

    # Set axis limits if provided
    if xlim:
        ax.set_xlim(xlim)
    if ylim:
        ax.set_ylim(ylim)

    ax.set_xlabel('Strain (mm/mm)', fontsize=12)
    ax.set_ylabel('Stress (MPa)', fontsize=12)
    ax.set_title(f'{test.comment}', fontsize=14)
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)

    # Add text box with key metrics
    textstr = f'E = {test.modulus:.0f} MPa\nσ_max = {test.max_stress:.1f} MPa\nε_max = {test.max_strain:.4f}'
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
    ax.text(0.95, 0.05, textstr, transform=ax.transAxes, fontsize=10,
            verticalalignment='bottom', horizontalalignment='right', bbox=props)

    plt.tight_layout()

    # Save plot
    safe_name = re.sub(r'[^\w\-_.]', '_', test.comment)
    plot_filename = f'plot_{safe_name}{get_plot_extension()}'
    plot_path = os.path.join(output_dir, plot_filename)
    save_plot(fig, plot_path)
    plt.close()

    return plot_filename


def create_comparison_plot(tests: list, output_dir: str,
                           xlim: tuple = None, ylim: tuple = None) -> str:
    """Create a comparison plot of all tests."""
    fig, ax = plt.subplots(figsize=(14, 8))

    colors = plt.cm.tab20(np.linspace(0, 1, len(tests)))
    for i, test in enumerate(sorted(tests, key=lambda x: x.comment)):
        ax.plot(test.df['Strain'].values, test.df['Stress_MPa'].values,
                color=colors[i], linewidth=1, label=test.comment, alpha=0.8)

    ax.set_xlabel('Strain (mm/mm)', fontsize=12)
    ax.set_ylabel('Stress (MPa)', fontsize=12)
    ax.set_title('Stress-Strain Curves - All Tests', fontsize=14)
    ax.legend(loc='center left', bbox_to_anchor=(1, 0.5), fontsize=8)
    ax.grid(True, alpha=0.3)
    if xlim:
        ax.set_xlim(xlim)
    if ylim:
        ax.set_ylim(ylim)

    plt.tight_layout()
    plot_filename = f'plot_comparison_all{get_plot_extension()}'
    save_plot(fig, os.path.join(output_dir, plot_filename))
    plt.close()

    return plot_filename


def create_material_comparison_bar_charts(tests: list, output_dir: str) -> dict:
    """Create bar charts comparing materials with error bars."""
    # Group tests by material
    materials = {}
    for test in tests:
        # Extract material name (first part before underscore or number pattern)
        material = re.split(r'[_\d]', test.comment)[0]
        if material not in materials:
            materials[material] = []
        materials[material].append(test)

    plot_files = {}

    # 1. Max Stress comparison
    fig, ax = plt.subplots(figsize=(12, 6))

    material_names = sorted(materials.keys())
    means = []
    stds = []
    counts = []

    for material in material_names:
        stresses = [t.max_stress for t in materials[material]]
        means.append(np.mean(stresses))
        stds.append(np.std(stresses) if len(stresses) > 1 else 0)
        counts.append(len(stresses))

    x = np.arange(len(material_names))
    bars = ax.bar(x, means, yerr=stds, capsize=5, color='steelblue', edgecolor='black', alpha=0.8)

    # Add count labels on bars
    for i, (bar, count) in enumerate(zip(bars, counts)):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + stds[i] + 1,
                f'n={count}', ha='center', va='bottom', fontsize=9)

    ax.set_xlabel('Material', fontsize=12)
    ax.set_ylabel('Max Stress (MPa)', fontsize=12)
    ax.set_title('Maximum Stress by Material', fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels(material_names, rotation=45, ha='right')
    ax.grid(True, axis='y', alpha=0.3)

    plt.tight_layout()
    plot_filename = f'plot_bar_max_stress{get_plot_extension()}'
    save_plot(fig, os.path.join(output_dir, plot_filename))
    plt.close()
    plot_files['max_stress'] = plot_filename

    # 2. Max Strain comparison
    fig, ax = plt.subplots(figsize=(12, 6))

    means = []
    stds = []

    for material in material_names:
        strains = [t.max_strain for t in materials[material]]
        means.append(np.mean(strains))
        stds.append(np.std(strains) if len(strains) > 1 else 0)

    bars = ax.bar(x, means, yerr=stds, capsize=5, color='forestgreen', edgecolor='black', alpha=0.8)

    for i, (bar, count) in enumerate(zip(bars, counts)):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + stds[i] + 0.005,
                f'n={count}', ha='center', va='bottom', fontsize=9)

    ax.set_xlabel('Material', fontsize=12)
    ax.set_ylabel('Max Strain (mm/mm)', fontsize=12)
    ax.set_title('Maximum Strain by Material', fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels(material_names, rotation=45, ha='right')
    ax.grid(True, axis='y', alpha=0.3)

    plt.tight_layout()
    plot_filename = f'plot_bar_max_strain{get_plot_extension()}'
    save_plot(fig, os.path.join(output_dir, plot_filename))
    plt.close()
    plot_files['max_strain'] = plot_filename

    # 3. Modulus comparison
    fig, ax = plt.subplots(figsize=(12, 6))

    means = []
    stds = []

    for material in material_names:
        moduli = [t.modulus for t in materials[material] if t.modulus > 0]
        if moduli:
            means.append(np.mean(moduli))
            stds.append(np.std(moduli) if len(moduli) > 1 else 0)
        else:
            means.append(0)
            stds.append(0)

    bars = ax.bar(x, means, yerr=stds, capsize=5, color='coral', edgecolor='black', alpha=0.8)

    for i, (bar, count) in enumerate(zip(bars, counts)):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + stds[i] + 20,
                f'n={count}', ha='center', va='bottom', fontsize=9)

    ax.set_xlabel('Material', fontsize=12)
    ax.set_ylabel('Modulus of Elasticity (MPa)', fontsize=12)
    ax.set_title('Modulus of Elasticity by Material', fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels(material_names, rotation=45, ha='right')
    ax.grid(True, axis='y', alpha=0.3)

    plt.tight_layout()
    plot_filename = f'plot_bar_modulus{get_plot_extension()}'
    save_plot(fig, os.path.join(output_dir, plot_filename))
    plt.close()
    plot_files['modulus'] = plot_filename

    return plot_files


def format_image_tag(filename: str, alt_text: str = "") -> str:
    """Format an image tag with explicit width."""
    return f'![{alt_text}]({filename}){{width="{PLOT_WIDTH}"}}'


def generate_qmd_report(tests: list, output_dir: str):
    """Generate the QMD report file."""

    # Calculate global axis limits for consistent plots
    all_strains = []
    all_stresses = []
    for test in tests:
        all_strains.extend(test.df['Strain'].values)
        all_stresses.extend(test.df['Stress_MPa'].values)

    xlim = (0, max(all_strains) * 1.05)
    ylim = (min(0, min(all_stresses) * 1.1), max(all_stresses) * 1.1)

    # Generate plots for each test
    print("Generating individual stress-strain plots...")
    plot_files = {}
    for i, test in enumerate(tests):
        print(f"  [{i+1}/{len(tests)}] {test.comment}")
        plot_files[test.filename] = create_stress_strain_plot(test, output_dir, xlim, ylim)

    # Generate comparison plot
    print("Generating comparison plot...")
    comparison_plot = create_comparison_plot(tests, output_dir, xlim, ylim)

    # Generate bar charts
    print("Generating material comparison bar charts...")
    bar_plots = create_material_comparison_bar_charts(tests, output_dir)

    # Group tests by material
    materials = {}
    for test in tests:
        material = re.split(r'[_\d]', test.comment)[0]
        if material not in materials:
            materials[material] = []
        materials[material].append(test)

    # Generate QMD content
    lines = []

    # Header
    lines.append('---')
    lines.append('title: "UTM Test Summary Report"')
    lines.append(f'date: "{datetime.now().strftime("%Y-%m-%d")}"')
    lines.append('format:')
    lines.append('  html:')
    lines.append('    toc: true')
    lines.append('    toc-depth: 3')
    lines.append('    code-fold: true')
    lines.append('    self-contained: true')
    lines.append('---')
    lines.append('')

    # Introduction
    lines.append('## Overview')
    lines.append('')
    lines.append(f'This report summarizes **{len(tests)}** tensile tests performed on the UTM (Universal Testing Machine).')
    lines.append(f'Tests span **{len(materials)}** different materials.')
    lines.append(f'Report generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.')
    lines.append('')

    # Summary Table
    lines.append('## Summary Table')
    lines.append('')
    lines.append('| Test Name | Max Stress (MPa) | Max Strain | Modulus E (MPa) | Duration (s) |')
    lines.append('|-----------|------------------|------------|-----------------|--------------|')

    for test in sorted(tests, key=lambda x: x.comment):
        lines.append(f'| {test.comment} | {test.max_stress:.2f} | {test.max_strain:.4f} | {test.modulus:.0f} | {test.duration:.1f} |')

    lines.append('')

    # Material Comparison Section
    lines.append('## Material Comparison')
    lines.append('')
    lines.append('### Maximum Stress')
    lines.append('')
    lines.append(format_image_tag(bar_plots['max_stress'], 'Max Stress by Material'))
    lines.append('')

    lines.append('### Maximum Strain')
    lines.append('')
    lines.append(format_image_tag(bar_plots['max_strain'], 'Max Strain by Material'))
    lines.append('')

    lines.append('### Modulus of Elasticity')
    lines.append('')
    lines.append(format_image_tag(bar_plots['modulus'], 'Modulus by Material'))
    lines.append('')

    # Statistics by Material
    lines.append('## Statistical Summary by Material')
    lines.append('')
    lines.append('| Material | n | Max Stress (MPa) | Max Strain | Modulus (MPa) |')
    lines.append('|----------|---|------------------|------------|---------------|')

    for material in sorted(materials.keys()):
        material_tests = materials[material]
        n = len(material_tests)
        stresses = [t.max_stress for t in material_tests]
        strains = [t.max_strain for t in material_tests]
        moduli = [t.modulus for t in material_tests if t.modulus > 0]

        stress_str = f'{np.mean(stresses):.1f} ± {np.std(stresses):.1f}' if n > 1 else f'{stresses[0]:.1f}'
        strain_str = f'{np.mean(strains):.4f} ± {np.std(strains):.4f}' if n > 1 else f'{strains[0]:.4f}'
        modulus_str = f'{np.mean(moduli):.0f} ± {np.std(moduli):.0f}' if len(moduli) > 1 else (f'{moduli[0]:.0f}' if moduli else 'N/A')

        lines.append(f'| {material} | {n} | {stress_str} | {strain_str} | {modulus_str} |')

    lines.append('')

    # Comparison Plot
    lines.append('## All Tests Comparison')
    lines.append('')
    lines.append(format_image_tag(comparison_plot, 'All Tests Comparison'))
    lines.append('')

    # Individual Test Results
    lines.append('## Individual Test Results')
    lines.append('')

    for material in sorted(materials.keys()):
        lines.append(f'### {material}')
        lines.append('')

        for test in sorted(materials[material], key=lambda x: x.comment):
            lines.append(f'#### {test.comment}')
            lines.append('')
            lines.append(f'- **Test Date**: {test.test_date}')
            lines.append(f'- **Duration**: {test.duration:.1f} s')
            lines.append(f'- **Data Points**: {test.data_points}')
            lines.append(f'- **Max Stress**: {test.max_stress:.2f} MPa')
            lines.append(f'- **Max Strain**: {test.max_strain:.4f}')
            lines.append(f'- **Modulus of Elasticity**: {test.modulus:.0f} MPa')
            lines.append(f'- **Linear Region**: {test.linear_start_strain:.4f} - {test.linear_end_strain:.4f} strain')
            lines.append('')
            lines.append(format_image_tag(plot_files[test.filename], test.comment))
            lines.append('')

    # Appendix
    lines.append('## Appendix: Test Parameters')
    lines.append('')
    lines.append('| Parameter | Value |')
    lines.append('|-----------|-------|')
    lines.append(f'| Specimen Area | {tests[0].area} mm² |')
    lines.append(f'| Gauge Length | {tests[0].gauge_length} mm |')
    lines.append(f'| Calibration Scale | {tests[0].scale} |')
    lines.append(f'| Calibration Offset | {tests[0].offset} |')
    lines.append(f'| App Version | {tests[0].app_version} |')
    lines.append('')

    # Write QMD file
    qmd_path = os.path.join(output_dir, 'UTM_Test_Summary_Report.qmd')
    with open(qmd_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f'Report generated: {qmd_path}')
    return qmd_path


def main():
    """Main entry point."""
    # Find all UTM CSV files in current directory
    csv_files = glob.glob('*_UTM_Test_*.csv')

    if not csv_files:
        print('No UTM CSV files found in current directory.')
        print('Looking for files matching pattern: *_UTM_Test_*.csv')
        return

    print(f'Found {len(csv_files)} UTM test files.')
    print(f'Plot format: {PLOT_FORMAT}, width: {PLOT_WIDTH}')
    print()

    # Load and process each test
    tests = []
    for filepath in csv_files:
        try:
            print(f'Loading: {filepath}')
            test = load_test_data(filepath)
            test = calculate_modulus(test)
            tests.append(test)
            print(f'  -> {test.comment}: E = {test.modulus:.0f} MPa')
        except Exception as e:
            print(f'  Error loading {filepath}: {e}')

    print()
    print(f'Successfully loaded {len(tests)} tests.')
    print()

    # Generate report
    output_dir = '.'
    generate_qmd_report(tests, output_dir)

    print()
    print('Done! To render the report, run:')
    print('  quarto render UTM_Test_Summary_Report.qmd')


if __name__ == '__main__':
    main()
