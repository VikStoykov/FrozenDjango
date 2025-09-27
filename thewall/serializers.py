from django.contrib.auth.models import Group, User
from rest_framework import serializers
import csv
import io


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ['url', 'username', 'email', 'groups']


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ['url', 'name']


class CSVUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        """
        Validate csv file
        """
        if not value.name.endswith('.csv'):
            raise serializers.ValidationError("Only CSV files are allowed.")

        # 50MB limit of file size
        if value.size > 50 * 1024 * 1024:
            raise serializers.ValidationError("File size too large. Maximum 50MB allowed.")

        # Validate config file based on requirements:
        # - Max 300 lines - The Wall Westeros is 300 miles long
        # - Max 2000 values per line
        # - Each value between 0 and 30
        try:
            value.seek(0)

            file_content = value.read().decode('utf-8')
            value.seek(0)

            csv_reader = csv.reader(io.StringIO(file_content))
            rows = list(csv_reader)

            if len(rows) > 300:
                raise serializers.ValidationError(f"Too many lines. Maximum 300 lines allowed, found {len(rows)} lines.")

            for row_num, row in enumerate(rows, 1):
                if not row or all(cell.strip() == '' for cell in row):
                    continue

                if len(row) > 2000:
                    raise serializers.ValidationError(f"Line {row_num}: Too many values. Maximum 2000 values per line allowed, found {len(row)} values.")

                for col_num, cell in enumerate(row, 1):
                    if cell.strip() == '':
                        continue

                    try:
                        value_int = int(cell.strip())
                        if not (0 <= value_int <= 30):
                            raise serializers.ValidationError(f"Line {row_num}, Column {col_num}: Value '{cell}' must be between 0 and 30.")
                    except ValueError:
                        raise serializers.ValidationError(f"Line {row_num}, Column {col_num}: Invalid number '{cell}'. All values must be numeric.")

            return value

        except UnicodeDecodeError:
            raise serializers.ValidationError("Invalid file encoding. Please use UTF-8 encoded CSV file.")
        except csv.Error as e:
            raise serializers.ValidationError(f"Invalid CSV format: {e}")
        except Exception as e:
            raise serializers.ValidationError(f"Error processing file: {str(e)}")
