from pathlib import Path
target_file = Path("scripts/dev/run_mutation_check.py")
content = target_file.read_text(encoding="utf-8")
content = content.replace(
    'print("  [2/16] Reverse subset caught (Siberian Airlines -> 🔴)")',
    'print("  [02/27] Mutation caught: Reverse subset sensitivity -> test_tiering.py::test_2_reverse_subset_airline")'
)
target_file.write_text(content, encoding="utf-8")
print("Done line 67")
