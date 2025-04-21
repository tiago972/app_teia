from django.shortcuts import render
from django.http import FileResponse
from .forms import DocxUploadForm
from django.core.files.storage import FileSystemStorage
import tempfile
import zipfile
import os
from scripts_teia_django import run 

def upload_file_view(request):
    if request.method == 'POST':
        form = DocxUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Récupération des champs
            docx_file = form.cleaned_data['docx_file']
            discipline = form.cleaned_data['discipline']
            annee = form.cleaned_data['annee']
            session = form.cleaned_data['session']
            titulaire = form.cleaned_data['titulaire']
            
            # Sauvegarder le fichier reçu
            fs = FileSystemStorage()
            filename = fs.save(docx_file.name, docx_file)
            input_path = fs.path(filename)

            # Créer un dossier temporaire pour les fichiers de sortie
            with tempfile.TemporaryDirectory() as output_dir:
                # Traiter le docx
                list_of_files = run(input_path, output_dir, discipline, annee, session, titulaire)
                
                # Créer un fichier ZIP dans ce même dossier
                zip_path = os.path.join(output_dir, 'teia_inputs.zip')
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for file_path in list_of_files:
                        zipf.write(file_path, arcname=os.path.basename(file_path))

                # Renvoyer le ZIP à télécharger
                fs.delete(filename)
                return FileResponse(open(zip_path, 'rb'), as_attachment=True, filename='teia_inputs.zip')
    else:
        form = DocxUploadForm()

    return render(request, 'upload.html', {'form': form})
