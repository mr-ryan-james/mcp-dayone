"""Day One CLI operations and tools."""

import subprocess
import json
import os
import sqlite3
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
import shlex


class DayOneError(Exception):
    """Exception raised for Day One CLI errors."""
    pass


class DayOneTools:
    """Wrapper for Day One CLI operations."""
    
    def __init__(self, cli_path: str | None = None):
        self.cli_path = cli_path or self._find_cli()
        self._verify_cli()
        self.db_path = self._get_db_path()

    @staticmethod
    def _find_cli() -> str:
        """Find the Day One CLI, trying 'dayone' first then 'dayone2'."""
        for name in ("dayone", "dayone2"):
            try:
                subprocess.run(
                    [name, "--version"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return name
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        raise DayOneError(
            "Day One CLI not found. Tried 'dayone' and 'dayone2'. "
            "Install via: sudo bash /Applications/Day\\ One.app/Contents/Resources/install_cli.sh"
        )

    def _verify_cli(self) -> None:
        """Verify Day One CLI is available."""
        try:
            result = subprocess.run(
                [self.cli_path, "--version"],
                capture_output=True,
                text=True,
                check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise DayOneError(
                f"Day One CLI '{self.cli_path}' not found or not working. "
                f"Please install Day One CLI first. Error: {e}"
            )
    
    def _get_db_path(self) -> Path:
        """Get the path to Day One database."""
        db_path = Path.home() / "Library/Group Containers/5U8NS4GX82.dayoneapp2/Data/Documents/DayOne.sqlite"
        return db_path
    
    def _get_db_connection(self) -> sqlite3.Connection:
        """Get a connection to the Day One database."""
        if not self.db_path.exists():
            raise DayOneError(
                f"Day One database not found at {self.db_path}. "
                "Make sure Day One app is installed and has been run at least once."
            )
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            return conn
        except sqlite3.Error as e:
            raise DayOneError(f"Failed to connect to Day One database: {e}")
    
    def create_entry(
        self,
        content: str,
        tags: Optional[List[str]] = None,
        date: Optional[str] = None,
        journal: Optional[str] = None,
        attachments: Optional[List[str]] = None,
        starred: Optional[bool] = None,
        coordinates: Optional[Dict[str, float]] = None,
        timezone: Optional[str] = None,
        all_day: Optional[bool] = None
    ) -> str:
        """Create a new Day One journal entry.
        
        Args:
            content: The entry text content
            tags: Optional list of tags to add
            date: Optional date string (YYYY-MM-DD HH:MM:SS format)
            journal: Optional journal name
            attachments: Optional list of file paths to attach (up to 10)
            starred: Optional flag to mark entry as starred
            coordinates: Optional dict with 'latitude' and 'longitude' keys
            timezone: Optional timezone string
            all_day: Optional flag to mark as all-day event
            
        Returns:
            UUID of the created entry
            
        Raises:
            DayOneError: If entry creation fails
        """
        if not content.strip():
            raise DayOneError("Entry content cannot be empty")
        
        # Validate attachments
        if attachments:
            if len(attachments) > 10:
                raise DayOneError("Maximum 10 attachments allowed per entry")
            
            for attachment in attachments:
                if not os.path.exists(attachment):
                    raise DayOneError(f"Attachment file not found: {attachment}")
        
        # Validate coordinates
        if coordinates:
            if 'latitude' not in coordinates or 'longitude' not in coordinates:
                raise DayOneError("Coordinates must include both 'latitude' and 'longitude'")
        
        # Build command
        cmd = [self.cli_path]
        
        # Add attachments
        if attachments:
            cmd.extend(["--attachments"] + attachments)
        
        # Add tags
        if tags:
            cmd.extend(["--tags"] + tags)
        
        # Add journal
        if journal:
            cmd.extend(["--journal", journal])
        
        # Add date
        if date:
            cmd.extend(["--date", date])
        
        # Add starred flag
        if starred:
            cmd.append("--starred")
        
        # Add coordinates
        if coordinates:
            coord_str = f"{coordinates['latitude']} {coordinates['longitude']}"
            cmd.extend(["--coordinate", coord_str])
        
        # Add timezone
        if timezone:
            cmd.extend(["--time-zone", timezone])
        
        # Add all-day flag
        if all_day:
            cmd.append("--all-day")
        
        # Add the command and content
        cmd.extend(["new", content])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Extract UUID from output
            output = result.stdout.strip()
            if "Created new entry with uuid:" in output:
                uuid = output.split("uuid:")[-1].strip()
                return uuid
            else:
                return output
                
        except subprocess.CalledProcessError as e:
            raise DayOneError(f"Failed to create entry: {e.stderr}")
    
    def list_journals(self) -> List[str]:
        """List available journals.
        
        Note: Day One CLI doesn't provide a direct way to list journals.
        This method returns a helpful message explaining the limitation.
        
        Returns:
            List with explanatory message
            
        Raises:
            DayOneError: If there's an issue
        """
        # Day One CLI doesn't have a journals command
        return [
            "Day One CLI doesn't provide a command to list journals.",
            "You can specify a journal name using the --journal parameter when creating entries.",
            "If no journal is specified, entries go to the default journal."
        ]
    
    def get_entry_count(self, journal: Optional[str] = None) -> int:
        """Get total number of entries.
        
        Note: Day One CLI doesn't provide a command to count entries.
        
        Args:
            journal: Optional journal name to count entries for
            
        Returns:
            Always returns -1 to indicate this functionality is not available
            
        Raises:
            DayOneError: If there's an issue
        """
        # Day One CLI doesn't have a list command
        raise DayOneError(
            "Day One CLI doesn't provide a command to count entries. "
            "You can view entry counts through the Day One app interface."
        )
    
    def read_recent_entries(self, limit: int = 10, journal: Optional[str] = None) -> List[Dict[str, Any]]:
        """Read recent journal entries from the database.
        
        Args:
            limit: Maximum number of entries to return
            journal: Optional journal name to filter by
            
        Returns:
            List of entry dictionaries with metadata
            
        Raises:
            DayOneError: If database access fails
        """
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Base query to get entries with journal information
            query = """
            SELECT 
                e.ZUUID as uuid,
                e.ZRICHTEXTJSON as rich_text,
                e.ZMARKDOWNTEXT as markdown_text,
                e.ZCREATIONDATE as creationDate,
                e.ZMODIFIEDDATE as modifiedDate,
                e.ZSTARRED as starred,
                e.ZTIMEZONE as timeZone,
                j.ZNAME as journal_name,
                e.ZLOCATION as location,
                e.ZWEATHER as weather
            FROM ZENTRY e
            LEFT JOIN ZJOURNAL j ON e.ZJOURNAL = j.Z_PK
            """
            
            params = []
            if journal:
                query += " WHERE j.ZNAME = ?"
                params.append(journal)
            
            query += " ORDER BY e.ZCREATIONDATE DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            entries = []
            
            for row in cursor.fetchall():
                # Extract text from rich text JSON or markdown
                text_content = self._extract_text_content(row['rich_text'], row['markdown_text'])
                
                entry = {
                    'uuid': row['uuid'],
                    'text': text_content or '',
                    'creation_date': datetime.fromtimestamp(row['creationDate'] + 978307200) if row['creationDate'] else None,  # Convert from Core Data timestamp
                    'modified_date': datetime.fromtimestamp(row['modifiedDate'] + 978307200) if row['modifiedDate'] else None,
                    'starred': bool(row['starred']),
                    'timezone': str(row['timeZone']) if row['timeZone'] else None,
                    'journal_name': row['journal_name'] or 'Default',
                    'has_location': bool(row['location']),
                    'has_weather': bool(row['weather'])
                }
                
                # Get tags for this entry
                entry['tags'] = self._get_entry_tags(cursor, row['uuid'])
                
                entries.append(entry)
            
            conn.close()
            return entries
            
        except sqlite3.Error as e:
            raise DayOneError(f"Failed to read entries from database: {e}")
    
    def _get_entry_tags(self, cursor: sqlite3.Cursor, entry_uuid: str) -> List[str]:
        """Get tags for a specific entry."""
        try:
            cursor.execute("""
                SELECT t.ZNAME 
                FROM ZTAG t
                JOIN Z_13TAGS zt ON t.Z_PK = zt.Z_55TAGS1
                JOIN ZENTRY e ON zt.Z_13ENTRIES = e.Z_PK
                WHERE e.ZUUID = ?
            """, (entry_uuid,))
            
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error:
            return []
    
    def search_entries(self, search_text: str, limit: int = 20, journal: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search journal entries by text content.
        
        Args:
            search_text: Text to search for in entry content
            limit: Maximum number of entries to return
            journal: Optional journal name to filter by
            
        Returns:
            List of entry dictionaries matching the search
            
        Raises:
            DayOneError: If database access fails
        """
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT 
                e.ZUUID as uuid,
                e.ZRICHTEXTJSON as rich_text,
                e.ZMARKDOWNTEXT as markdown_text,
                e.ZCREATIONDATE as creationDate,
                e.ZMODIFIEDDATE as modifiedDate,
                e.ZSTARRED as starred,
                e.ZTIMEZONE as timeZone,
                j.ZNAME as journal_name
            FROM ZENTRY e
            LEFT JOIN ZJOURNAL j ON e.ZJOURNAL = j.Z_PK
            WHERE (e.ZRICHTEXTJSON LIKE ? OR e.ZMARKDOWNTEXT LIKE ?)
            """
            
            params = [f'%{search_text}%', f'%{search_text}%']
            
            if journal:
                query += " AND j.ZNAME = ?"
                params.append(journal)
            
            query += " ORDER BY e.ZCREATIONDATE DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            entries = []
            
            for row in cursor.fetchall():
                # Extract text from rich text JSON or markdown
                text_content = self._extract_text_content(row['rich_text'], row['markdown_text'])
                
                entry = {
                    'uuid': row['uuid'],
                    'text': text_content or '',
                    'creation_date': datetime.fromtimestamp(row['creationDate'] + 978307200) if row['creationDate'] else None,
                    'modified_date': datetime.fromtimestamp(row['modifiedDate'] + 978307200) if row['modifiedDate'] else None,
                    'starred': bool(row['starred']),
                    'timezone': str(row['timeZone']) if row['timeZone'] else None,
                    'journal_name': row['journal_name'] or 'Default'
                }
                
                entry['tags'] = self._get_entry_tags(cursor, row['uuid'])
                entries.append(entry)
            
            conn.close()
            return entries
            
        except sqlite3.Error as e:
            raise DayOneError(f"Failed to search entries: {e}")
    
    def list_journals_from_db(self) -> List[Dict[str, Any]]:
        """List all journals from the database with entry counts.
        
        Returns:
            List of journal dictionaries with metadata
            
        Raises:
            DayOneError: If database access fails
        """
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    j.ZNAME as name,
                    j.ZUUIDFORAUXILIARYSYNC as uuid,
                    COUNT(e.Z_PK) as entry_count,
                    MAX(e.ZCREATIONDATE) as last_entry_date
                FROM ZJOURNAL j
                LEFT JOIN ZENTRY e ON e.ZJOURNAL = j.Z_PK
                GROUP BY j.Z_PK, j.ZNAME, j.ZUUIDFORAUXILIARYSYNC
                ORDER BY j.ZNAME
            """)
            
            journals = []
            for row in cursor.fetchall():
                journal = {
                    'name': row['name'],
                    'uuid': row['uuid'],
                    'entry_count': row['entry_count'],
                    'last_entry_date': datetime.fromtimestamp(row['last_entry_date'] + 978307200) if row['last_entry_date'] else None
                }
                journals.append(journal)
            
            conn.close()
            return journals
            
        except sqlite3.Error as e:
            raise DayOneError(f"Failed to list journals from database: {e}")
    
    def get_entry_count_from_db(self, journal: Optional[str] = None) -> int:
        """Get actual entry count from database.
        
        Args:
            journal: Optional journal name to count entries for
            
        Returns:
            Number of entries
            
        Raises:
            DayOneError: If database access fails
        """
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            if journal:
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM ZENTRY e
                    JOIN ZJOURNAL j ON e.ZJOURNAL = j.Z_PK
                    WHERE j.ZNAME = ?
                """, (journal,))
            else:
                cursor.execute("SELECT COUNT(*) FROM ZENTRY")
            
            count = cursor.fetchone()[0]
            conn.close()
            return count
            
        except sqlite3.Error as e:
            raise DayOneError(f"Failed to count entries from database: {e}")
    
    def _extract_text_content(self, rich_text_json: Optional[str], markdown_text: Optional[str]) -> str:
        """Extract readable text content from Day One's rich text JSON or markdown.
        
        Args:
            rich_text_json: Rich text JSON string from Day One
            markdown_text: Markdown text alternative
            
        Returns:
            Extracted text content
        """
        if not rich_text_json and not markdown_text:
            return ""
        
        # Try to extract from rich text JSON first
        if rich_text_json:
            try:
                rich_data = json.loads(rich_text_json)
                
                # Handle different rich text JSON structures
                if isinstance(rich_data, dict):
                    # Look for common text fields in Day One's rich text format
                    if 'text' in rich_data:
                        return str(rich_data['text']).strip()
                    
                    # Handle attributedString format
                    if 'attributedString' in rich_data:
                        attr_string = rich_data['attributedString']
                        if isinstance(attr_string, dict) and 'string' in attr_string:
                            return str(attr_string['string']).strip()
                    
                    # Handle ops format (similar to Quill.js delta format)
                    if 'ops' in rich_data:
                        text_parts = []
                        for op in rich_data['ops']:
                            if isinstance(op, dict) and 'insert' in op:
                                insert_value = op['insert']
                                if isinstance(insert_value, str):
                                    text_parts.append(insert_value)
                                elif isinstance(insert_value, dict) and 'text' in insert_value:
                                    text_parts.append(str(insert_value['text']))
                        return ''.join(text_parts).strip()
                    
                    # Handle delta format
                    if 'delta' in rich_data:
                        delta = rich_data['delta']
                        if isinstance(delta, dict) and 'ops' in delta:
                            text_parts = []
                            for op in delta['ops']:
                                if isinstance(op, dict) and 'insert' in op:
                                    text_parts.append(str(op['insert']))
                            return ''.join(text_parts).strip()
                    
                    # Handle NSAttributedString format (macOS native)
                    if 'NSString' in rich_data:
                        return str(rich_data['NSString']).strip()
                    
                    # Fallback: try to find any string values in the JSON
                    def extract_strings(obj, max_depth=3):
                        if max_depth <= 0:
                            return []
                        
                        strings = []
                        if isinstance(obj, str) and len(obj.strip()) > 0:
                            strings.append(obj.strip())
                        elif isinstance(obj, dict):
                            for value in obj.values():
                                strings.extend(extract_strings(value, max_depth - 1))
                        elif isinstance(obj, list):
                            for item in obj:
                                strings.extend(extract_strings(item, max_depth - 1))
                        return strings
                    
                    extracted_strings = extract_strings(rich_data)
                    if extracted_strings:
                        # Return the longest meaningful string
                        meaningful_strings = [s for s in extracted_strings if len(s) > 10]
                        if meaningful_strings:
                            return max(meaningful_strings, key=len)
                        elif extracted_strings:
                            return extracted_strings[0]
                
                elif isinstance(rich_data, str):
                    return rich_data.strip()
                
            except (json.JSONDecodeError, KeyError, TypeError):
                # If JSON parsing fails, try to extract plain text from the raw string
                if rich_text_json.strip():
                    # Remove common JSON artifacts and extract readable text
                    # Remove JSON structure characters but keep content
                    cleaned = re.sub(r'[{}\[\]"]', ' ', rich_text_json)
                    cleaned = re.sub(r'\\n', '\n', cleaned)
                    cleaned = re.sub(r'\\t', '\t', cleaned)
                    cleaned = re.sub(r'\s+', ' ', cleaned)
                    
                    # Look for sentences (text with punctuation and reasonable length)
                    sentences = re.findall(r'[A-Z][^.!?]*[.!?]', cleaned)
                    if sentences:
                        return ' '.join(sentences[:3]).strip()  # First few sentences
                    
                    # Fallback to first meaningful chunk
                    words = cleaned.split()
                    meaningful_words = [w for w in words if len(w) > 2 and w.isalpha()]
                    if len(meaningful_words) >= 5:
                        return ' '.join(meaningful_words[:20]).strip()
        
        # Fallback to markdown text
        if markdown_text:
            return markdown_text.strip()
        
        return ""
    
    def get_entries_by_date(self, target_date: str, years_back: int = 5) -> List[Dict[str, Any]]:
        """Get journal entries for a specific date across multiple years ('On This Day').
        
        Args:
            target_date: Target date in MM-DD format (e.g., '06-14' for June 14th)
            years_back: How many years back to search (default 5)
            
        Returns:
            List of entries from this date in previous years
            
        Raises:
            DayOneError: If database access fails
        """
        try:
            # Parse and validate date format
            from datetime import datetime, timedelta
            
            # Handle different date formats
            if len(target_date) == 5 and '-' in target_date:  # MM-DD
                month, day = target_date.split('-')
            elif len(target_date) == 10:  # YYYY-MM-DD
                month, day = target_date.split('-')[1:3]
            else:
                # Try parsing various formats
                try:
                    parsed_date = datetime.strptime(target_date, '%Y-%m-%d')
                    month, day = f"{parsed_date.month:02d}", f"{parsed_date.day:02d}"
                except ValueError:
                    try:
                        parsed_date = datetime.strptime(target_date, '%m-%d')
                        month, day = f"{parsed_date.month:02d}", f"{parsed_date.day:02d}"
                    except ValueError:
                        raise DayOneError(f"Invalid date format: {target_date}. Use MM-DD or YYYY-MM-DD format.")
            
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Get current year to search backwards
            current_year = datetime.now().year
            
            # Build query to find entries on this date across multiple years
            date_conditions = []
            params = []
            
            for year in range(current_year - years_back, current_year + 1):
                # Create date range for the full day
                start_date = datetime(year, int(month), int(day))
                end_date = start_date + timedelta(days=1)
                
                # Convert to Core Data timestamp (seconds since 2001-01-01)
                start_timestamp = (start_date.timestamp() - 978307200)
                end_timestamp = (end_date.timestamp() - 978307200)
                
                date_conditions.append("(e.ZCREATIONDATE >= ? AND e.ZCREATIONDATE < ?)")
                params.extend([start_timestamp, end_timestamp])
            
            query = f"""
            SELECT 
                e.ZUUID as uuid,
                e.ZRICHTEXTJSON as rich_text,
                e.ZMARKDOWNTEXT as markdown_text,
                e.ZCREATIONDATE as creationDate,
                e.ZMODIFIEDDATE as modifiedDate,
                e.ZSTARRED as starred,
                e.ZTIMEZONE as timeZone,
                j.ZNAME as journal_name,
                e.ZLOCATION as location,
                e.ZWEATHER as weather
            FROM ZENTRY e
            LEFT JOIN ZJOURNAL j ON e.ZJOURNAL = j.Z_PK
            WHERE ({' OR '.join(date_conditions)})
            ORDER BY e.ZCREATIONDATE DESC
            """
            
            cursor.execute(query, params)
            entries = []
            
            for row in cursor.fetchall():
                # Extract text content
                text_content = self._extract_text_content(row['rich_text'], row['markdown_text'])
                
                entry_date = datetime.fromtimestamp(row['creationDate'] + 978307200) if row['creationDate'] else None
                
                entry = {
                    'uuid': row['uuid'],
                    'text': text_content or '',
                    'creation_date': entry_date,
                    'modified_date': datetime.fromtimestamp(row['modifiedDate'] + 978307200) if row['modifiedDate'] else None,
                    'starred': bool(row['starred']),
                    'timezone': str(row['timeZone']) if row['timeZone'] else None,
                    'journal_name': row['journal_name'] or 'Default',
                    'has_location': bool(row['location']),
                    'has_weather': bool(row['weather']),
                    'year': entry_date.year if entry_date else None,
                    'years_ago': current_year - entry_date.year if entry_date else None
                }
                
                # Get tags for this entry
                entry['tags'] = self._get_entry_tags(cursor, row['uuid'])
                
                entries.append(entry)
            
            conn.close()
            return entries
            
        except sqlite3.Error as e:
            raise DayOneError(f"Failed to get entries by date: {e}")
        except ValueError as e:
            raise DayOneError(f"Date parsing error: {e}")