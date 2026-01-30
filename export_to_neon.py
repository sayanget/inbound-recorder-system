#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Export SQLite database to PostgreSQL (Neon) compatible SQL
"""
import sqlite3
import os

# Database path
DB_PATH = 'inbound.db'

def sqlite_to_postgres_type(sqlite_type):
    """Convert SQLite types to PostgreSQL types"""
    type_map = {
        'INTEGER': 'INTEGER',
        'TEXT': 'TEXT',
        'REAL': 'REAL',
        'BLOB': 'BYTEA',
        'DATETIME': 'TIMESTAMP',
        'DATE': 'DATE',
        'BOOLEAN': 'BOOLEAN'
    }
    
    sqlite_type_upper = sqlite_type.upper()
    for key in type_map:
        if key in sqlite_type_upper:
            return type_map[key]
    return 'TEXT'  # Default to TEXT

def export_schema_and_data():
    """Export SQLite schema and data to PostgreSQL SQL file"""
    
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file {DB_PATH} not found!")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = cursor.fetchall()
    
    output_file = 'neon_deploy.sql'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("-- PostgreSQL Schema and Data Export from SQLite\n")
        f.write("-- Generated for Neon Database\n\n")
        
        # Drop existing tables
        f.write("-- Drop existing tables if they exist\n")
        for table in tables:
            table_name = table[0]
            f.write(f"DROP TABLE IF EXISTS {table_name} CASCADE;\n")
        f.write("\n")
        
        # Create tables
        for table in tables:
            table_name = table[0]
            print(f"Processing table: {table_name}")
            
            # Get table schema
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            f.write(f"-- Table: {table_name}\n")
            f.write(f"CREATE TABLE {table_name} (\n")
            
            column_defs = []
            for col in columns:
                col_id, col_name, col_type, not_null, default_val, is_pk = col
                
                # Convert type
                pg_type = sqlite_to_postgres_type(col_type)
                
                # Build column definition
                col_def = f"    {col_name} "
                
                # Handle PRIMARY KEY with AUTOINCREMENT
                if is_pk and 'INTEGER' in col_type.upper():
                    col_def += "SERIAL PRIMARY KEY"
                else:
                    col_def += pg_type
                    
                    if not_null and not is_pk:
                        col_def += " NOT NULL"
                    
                    if default_val is not None:
                        if default_val == 'CURRENT_TIMESTAMP':
                            col_def += " DEFAULT CURRENT_TIMESTAMP"
                        elif default_val.isdigit():
                            col_def += f" DEFAULT {default_val}"
                        else:
                            col_def += f" DEFAULT '{default_val}'"
                
                column_defs.append(col_def)
            
            f.write(",\n".join(column_defs))
            f.write("\n);\n\n")
            
            # Export data
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            
            if rows:
                f.write(f"-- Data for table: {table_name}\n")
                
                # Get column names
                col_names = [col[1] for col in columns if col[1] != 'id' or not col[5]]  # Exclude auto-increment id
                
                for row in rows:
                    # Filter out auto-increment id column
                    filtered_row = []
                    filtered_cols = []
                    
                    for i, col in enumerate(columns):
                        # Skip auto-increment primary key
                        if col[5] and 'INTEGER' in col[2].upper():
                            continue
                        filtered_cols.append(col[1])
                        filtered_row.append(row[i])
                    
                    if filtered_row:
                        # Format values
                        values = []
                        for val in filtered_row:
                            if val is None:
                                values.append('NULL')
                            elif isinstance(val, (int, float)):
                                values.append(str(val))
                            else:
                                # Escape single quotes
                                escaped_val = str(val).replace("'", "''")
                                values.append(f"'{escaped_val}'")
                        
                        cols_str = ", ".join(filtered_cols)
                        vals_str = ", ".join(values)
                        f.write(f"INSERT INTO {table_name} ({cols_str}) VALUES ({vals_str});\n")
                
                f.write("\n")
    
    conn.close()
    print(f"\nExport completed! SQL file saved to: {output_file}")
    print(f"\nTo deploy to Neon, run:")
    print(f"psql 'postgresql://neondb_owner:npg_G1pxCJTigOK2@ep-green-meadow-afwsztqi-pooler.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require' < {output_file}")

if __name__ == '__main__':
    export_schema_and_data()
