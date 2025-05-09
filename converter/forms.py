# converter/forms.py

from django import forms

SESSION_CHOICES = [
    ('CC', 'Contrôle continu'),
    ('S1', 'Session 1'),
    ('S2', 'Session 2'),
]

class DocxUploadForm(forms.Form):
    docx_file = forms.FileField(label="Fichier .docx", required = True)
    discipline = forms.CharField(label="Discipline", max_length=100, required = True)
    annee = forms.CharField(label="Année", max_length=4, required = True)
    session = forms.ChoiceField(label="Session", choices=SESSION_CHOICES, required = True)
    titulaire = forms.CharField(label="Titulaire", max_length=100, required = True)
