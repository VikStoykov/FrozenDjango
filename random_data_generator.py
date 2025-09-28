import csv
import random

lines = 300
max_values_per_line = 2000
value_range = (0, 30)

print('Generating large CSV file...')

with open('test_data/test_valid_big.csv', 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)

    for line_num in range(1, lines + 1):
        num_values = random.randint(1, max_values_per_line)

        row = [random.randint(value_range[0], value_range[1]) for _ in range(num_values)]

        writer.writerow(row)

        if line_num % 50 == 0:
            print(f'Generated {line_num}/{lines} lines...')

print('CSV file generated successfully!')
print(f'File: test_data/test_valid_big.csv')
print(f'Lines: {lines}')
print(f'Max values per line: {max_values_per_line}')
print(f'Value range: {value_range[0]}-{value_range[1]}')
