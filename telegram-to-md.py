from bs4 import BeautifulSoup, NavigableString
import os
import re
from datetime import datetime
import emoji

def clean_filename(text):
    """Convert text to a valid filename by removing invalid characters and emojis."""
    # Remove emojis
    text = emoji.replace_emoji(text, '')
    
    # Remove special characters and replace with spaces
    clean = re.sub(r'[<>:"/\\|?*\n\r]', ' ', text)
    
    # Remove punctuation marks at the end
    clean = re.sub(r'[.,!?;:]+$', '', clean)
    
    # Replace multiple spaces with single space and trim
    clean = re.sub(r'\s+', ' ', clean).strip()
    
    # Limit length to 100 characters but try to cut at word boundary
    if len(clean) > 100:
        clean = clean[:100].rsplit(' ', 1)[0]
    
    return clean

def get_tags_from_content(text, author):
    """Extract tags based on text content and author name."""
    tags = set()
    
    # Combine text and author for searching
    search_text = (text + ' ' + author).lower()
    
    # Design-related tags
    if any(term in search_text for term in ['design', 'дизайн', 'ux', 'ui']):
        tags.add('design')
    
    # Product-related tags
    if any(term in search_text for term in ['product', 'продакт', 'продукт']):
        tags.add('product')
        
    # Management list tags
    if any(term in search_text for term in ['team', 'тимлид', 'команд']):
        tags.add('management')
        
    return sorted(list(tags))

def extract_first_meaningful_line(text):
    """Extract the first meaningful line of text, handling various edge cases."""
    # Split by newlines and filter out empty lines
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    # Return the first line that has more than 10 characters
    for line in lines:
        if len(line) >= 10:
            return line
    
    # If no line is found with more than 10 characters, return the first non-empty line if available
    if lines:
        return lines[0]
    
    # If no meaningful line is found, return None
    return None

def convert_tag_to_md(tag):
    """Convert HTML tag to Markdown while preserving formatting."""
    if tag is None:
        return ""
        
    parts = []
    for child in tag.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif child.name in ['strong', 'b']:
            content = convert_tag_to_md(child).strip()
            if content:  # Only add formatting if content isn't empty
                parts.append(f"**{content}**")
        elif child.name in ['em', 'i']:
            content = convert_tag_to_md(child).strip()
            if content:
                parts.append(f"*{content}*")
        elif child.name == 'code':
            parts.append(f"`{convert_tag_to_md(child)}`")
        elif child.name == 'pre':
            parts.append(f"```\n{convert_tag_to_md(child).strip()}\n```")
        elif child.name == 'a':
            text = child.get_text().strip()
            href = child.get('href', '')
            if text and href:
                parts.append(f"[{text}]({href})")
            elif href:
                parts.append(href)
        elif child.name == 'br':
            parts.append('\n')
        elif child.name == 'ul':
            # Handle unordered lists
            items = child.find_all('li', recursive=False)
            for item in items:
                parts.append(f"* {convert_tag_to_md(item).strip()}\n")
        elif child.name == 'ol':
            # Handle ordered lists
            items = child.find_all('li', recursive=False)
            for i, item in enumerate(items, 1):
                parts.append(f"{i}. {convert_tag_to_md(item).strip()}\n")
        elif child.name == 'li':
            # Handle list items without adding extra markers
            parts.append(convert_tag_to_md(child))
        elif child.name == 'div':
            # Handle nested divs by recursing
            div_content = convert_tag_to_md(child)
            if div_content:
                parts.append(div_content + '\n')
        else:
            parts.append(convert_tag_to_md(child))
    
    return ''.join(parts)

def extract_title_and_date(message):
    """Extract title from message content and date."""
    text_div = message.select_one('.text')
    date_div = message.select_one('.date')
    
    if not text_div:
        return None, None

    # Get the complete text content and clean it, replacing ‹br> with newlines
    text = convert_tag_to_md(text_div) # Convert HTML to Markdown
    
    # Extract the first meaningful line from cleaned text
    first_line = extract_first_meaningful_line(text)
    
    if not first_line:
        return None, None
    
    # Extract date if available
    date_str = None
    if date_div:
        date_title = date_div.get('title', '')
        try:
            date_obj = datetime.strptime(date_title.split()[0], '%d.%m.%Y')
            date_str = date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
            
    title = clean_filename(first_line)
    return title, date_str

def convert_html_to_md(html_path, output_dir):
    """Convert Telegram HTML export to individual Markdown files."""
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
    except FileNotFoundError:
        print(f"Error: The file {html_path} was not found.")
        return
    except Exception as e:
        print(f"An error occurred: {e}")
        return
    
    # Find all regular messages (excluding service messages)
    messages = soup.select('.message.default.clearfix')
    
    # Keep track of the last known author
    last_author = "Unknown Author"
    
    # Keep track of used filenames for handling duplicates
    used_filenames = set()
    converted_count = 0
    
    for message in messages:
        # Extract message content
        text_div = message.select_one('.text')
        if not text_div or not text_div.get_text().strip():
            continue
            
        # Extract author
        author_div = message.select_one('.from_name')
#        author = author_div.get_text().strip() if author_div else "Unknown Author"
        author = author_div.get_text().strip() if author_div else last_author
        
        # Convert content to markdown while preserving formatting
        md_content = convert_tag_to_md(text_div)
        md_content = re.sub(r'\n{3,}', '\n\n', md_content)  # Remove excessive newlines
        
        # Get tags based on content and author
        tags = get_tags_from_content(md_content, author)
        
        # Get title and date for filename
        title, date_str = extract_title_and_date(message)
        if not title:
            continue
            
        # Create filename
        filename = f"{title}.md"
        
#        # Handle duplicate filenames only if necessary
#        if filename in used_filenames:
#            counter = 1
#            base_title = title.rsplit('.', 1)[0]  # Remove extension if present
#            while True:
#                new_filename = f"{base_title}_{counter}.md"
#                if new_filename not in used_filenames:
#                    filename = new_filename
#                    break
#                counter += 1

        # Check for duplicates and skip if found
        if filename in used_filenames:
            # print(f"Duplicate filename found: '{filename}'. Skipping this message.")
            continue
        
        used_filenames.add(filename)
        
        # Create markdown content with frontmatter
        frontmatter = ['---']
        if date_str:
            frontmatter.append(f'date: {date_str}')
        frontmatter.append(f'author: "{author}"')
        if tags:
            frontmatter.append('tags:')
            for tag in tags:
                frontmatter.append(f'  - {tag}')
        frontmatter.extend(['---\n', md_content])
        
        final_content = '\n'.join(frontmatter)
        
        # Write to file
        output_path = os.path.join(output_dir, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
        
        converted_count += 1
#        print(f"Created: {filename}")
    
    print(f"\nConversion completed! Converted {converted_count} messages.")

if __name__ == "__main__":
    html_path = "messages.html"
    output_dir = "telegram_messages"
    
    convert_html_to_md(html_path, output_dir)