from django.shortcuts import render
from django.http import FileResponse
from .forms import DocxUploadForm
from django.core.files.storage import FileSystemStorage
from django.core.files import File
import tempfile
import zipfile
import os
import shutil
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
                try:
                    # Traiter le fichier
                    list_of_files = run(input_path, output_dir, discipline, annee, session, titulaire)

                    # Créer un fichier ZIP dans output_dir
                    zip_path = os.path.join(output_dir, 'teia_inputs.zip')
                    with zipfile.ZipFile(zip_path, 'w') as zipf:
                        for file_path in list_of_files:
                            zipf.write(file_path, arcname=os.path.basename(file_path))

                    # Copier le ZIP dans /tmp pour qu'il survive après le with
                    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip', dir='/tmp')
                    with open(zip_path, 'rb') as f_in, open(temp_zip.name, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)

                    # Supprimer le fichier original
                    fs.delete(filename)

                    # Renvoyer le fichier en téléchargement
                    return FileResponse(File(open(temp_zip.name, 'rb')), as_attachment=True, filename='teia_inputs.zip')
                except Exception as e:
                    fs.delete(filename)
                    return render(request, 'upload.html', {
                        'form': form,
                        'error': f"Erreur lors du traitement : {str(e)}"
                    })
    else:
        form = DocxUploadForm()

    return render(request, 'upload.html', {'form': form})
