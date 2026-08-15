from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

out = Path(__file__).parent
font = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
pdfmetrics.registerFont(TTFont('DejaVu', font))

def make_pdf(path, title, sections):
    canvas = Canvas(str(path), pagesize=A4)
    width, height = A4
    canvas.setFont('DejaVu', 18)
    y = height - 70
    for text in [title] + [line for pair in sections for line in pair]:
        canvas.drawString(55, y, text)
        y -= 32 if text == title else 24
        if y < 70:
            canvas.showPage(); canvas.setFont('DejaVu', 12); y = height - 70
    canvas.save()

make_pdf(out / 'english-data-structures.pdf', 'Python Data Structures', [
    ('This practical guide introduces core data structures used in Python programming.', ''),
    ('Lists and Tuples', 'Lists are ordered, mutable collections. Tuples are ordered collections that cannot be changed after creation.'),
    ('Dictionaries', 'Dictionaries store key-value pairs and provide fast lookup by key.'),
    ('Learning Objectives', 'Learners can choose a suitable data structure and explain its trade-offs.')
])
make_pdf(out / 'arabic-data-structures.pdf', 'أساسيات هياكل البيانات', [
    ('مقدمة', 'يقدم هذا الدليل مقدمة عملية إلى هياكل البيانات الأساسية المستخدمة في البرمجة بلغة بايثون.'),
    ('القوائم والصفوف', 'القوائم مجموعات مرتبة قابلة للتغيير، بينما الصفوف مجموعات مرتبة لا يمكن تعديلها.'),
    ('القواميس', 'تخزن القواميس أزواجاً من المفتاح والقيمة وتوفر وصولاً سريعاً إلى البيانات.'),
    ('أهداف التعلم', 'يستطيع المتعلم اختيار هيكل البيانات المناسب وشرح الفروق بين الهياكل المختلفة.')
])
for p in (out / 'english-data-structures.pdf', out / 'arabic-data-structures.pdf'):
    assert p.exists() and p.stat().st_size > 1000
    print(p)
