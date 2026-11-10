with open('modules/ownership/ui.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('["📁 Excel Upload & Preview", "📄 Word (.docx) Import", "⚙️ Mappings & Settings"]', '["Excel Upload & Preview", "Word (.docx) Import", "Mappings & Settings"]')

with open('modules/ownership/ui.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Ownership tabs updated successfully!')
