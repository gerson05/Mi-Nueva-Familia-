import json
with open('analysis_result.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

lines = []
lines.append("ALL SHEETS:")
for s in data['sheets']:
    lines.append(f"  [{s}]")

lines.append("")
lines.append("CALI TRONCAL rows (first 15, cols 0-6):")
rows = data.get('cali_first_rows', [])
for i, row in enumerate(rows):
    lines.append(f"R{i}: {row[:7]}")

lines.append("")
lines.append("WORD PARAGRAPHS:")
for p in data.get('word_paragraphs', []):
    lines.append(f"  {p}")

lines.append("")
lines.append("WORD TABLES:")
tables = data.get('word_tables', [])
for ti, table in enumerate(tables):
    lines.append(f"TABLE {ti}:")
    for ri, row in enumerate(table):
        lines.append(f"  Row {ri}: {row}")

with open('structure_report.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print("Report saved")
