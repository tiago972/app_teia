# Script complet pour transformer un DOCX friendly en ZIP QTI (QI en GIFT + QROC en XML) + KFP (QTI XML)

from docx import Document
import re
import html
import zipfile
import os
import argparse
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

# Paramètres globaux par défaut
invisible = ['\u00A0', '\u200B', '\u200C', '\u200D', '\u2060', '\uFEFF']
clean = lambda text: ''.join(c for c in text if c not in invisible)

def parse_docx(path):
    doc = Document(path)
    paragraphs = [p.text.strip() for p in doc.paragraphs]
    qi_list, kfp_list = [], []
    i = 0
    while i < len(paragraphs):
        while i < len(paragraphs) and paragraphs[i] not in ("[QI]", "[KFP]"):
          i += 1
        if paragraphs[i] == "[QI]":
            i += 1
            question_text = paragraphs[i]  
            choices = []
            i += 1
            while i < len(paragraphs) and not paragraphs[i].startswith(("[QI]", "[KFP]")):
                line_raw = paragraphs[i]
                is_correct = line_raw.endswith("*")
                line = re.sub(r"^\s*([A-Z]\.|[-•–])\s*", "", line_raw)
                text = re.sub(r"\s*\*$", "", line).strip()
                choices.append((text, is_correct))
                i += 1
            nb_correct = sum(1 for _, c in choices if c)
            if nb_correct == 0:
                qtype = "qroc"
            elif nb_correct == 1:
                qtype = "qru"
            elif "#QRP" in question_text:
                question_text = question_text.replace("#QRP", "").strip()
                qtype = "qrp"
            else:
                qtype = "qrm"
            qi_list.append({"type": qtype, "question": question_text, "choices": choices})

        elif paragraphs[i] == "[KFP]":
            i += 1
            while i < len(paragraphs) and not paragraphs[i].strip():
              i += 1
            vignette = paragraphs[i]
            i += 1
            questions = []
            while i < len(paragraphs) and not paragraphs[i].startswith("["):
              if clean(paragraphs[i]).lower().startswith("q:"):
                  q_text = clean(paragraphs[i])
                  q_text = q_text[2:].strip()
                  i += 1
                  subchoices = []
                  while i < len(paragraphs) and not paragraphs[i].startswith(("[QI]", "[QROC]", "[KFP]")) and not clean(paragraphs[i]).lower().startswith("q:"):
                      line_raw = paragraphs[i]
                      if not line_raw.strip():
                          i += 1
                          continue
                      is_correct = line_raw.endswith("*")
                      line = re.sub(r"^\s*([A-Z]\.|[-•–])\s*", "", line_raw)
                      text = re.sub(r"\s*\*$", "", line).strip()
                      subchoices.append((text, is_correct))
                      i += 1
                  nb_correct = sum(1 for _, c in subchoices if c)
                  subtype = "qroc" if nb_correct == 0 else "qcm"
                  questions.append({"question": q_text, "choices": subchoices, "type": subtype})
              else:
                  i += 1
            kfp_list.append({"vignette": vignette, "questions": questions})
        else:
            i += 1
    return qi_list, kfp_list

def generate_gift(qi_list, output_dir, discipline, annee, session, titulaire):
    """
    Crée un fichier GIFT à partir des questions et le compresse en ZIP.
    Retourne le chemin complet vers le ZIP créé.
    """
    gift_lines = []
    for idx, q in enumerate(qi_list, 1):
        nom = f"{discipline}-{annee}-{session}-QI N°{idx}-{titulaire}"
        gift_lines.append(f"::{nom}::{q['question']} {{")
        for choice, is_correct in q['choices']:
            if q["type"] == "qcm":
                if choice:
                    percent = "100" if is_correct else "-100"
                    gift_lines.append(f"~%{percent}% {choice}")
            elif q["type"] == "qroc":
                if choice:
                    gift_lines.append(f"={choice}")
        gift_lines.append("}\n")

    # Sauvegarder dans le dossier temporaire
    gift_path = os.path.join(output_dir, "questions.gift")
    with open(gift_path, "w", encoding="utf-8") as f:
        f.write("\n".join(gift_lines))

    # Créer le ZIP
    zip_path = os.path.join(output_dir, "gift_output.zip")
    with zipfile.ZipFile(zip_path, "w") as zipf:
        zipf.write(gift_path, arcname="questions.gift")

    # Supprimer le .gift si tu veux
    os.remove(gift_path)

    return zip_path

def generate_qti_qcm(identifier, title, question_text, choices):
    root = Element("assessmentItem", attrib={
        "xmlns": "http://www.imsglobal.org/xsd/imsqti_v2p1",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "identifier": identifier,
        "title": title,
        "adaptive": "false",
        "timeDependent": "false",
        "toolName": "Theia",
        "xsi:schemaLocation": "http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/qti/qtiv2p1/imsqti_v2p1.xsd"
    })
    response = SubElement(root, "responseDeclaration", identifier="RESPONSE", cardinality="multiple", baseType="identifier")
    correct = SubElement(response, "correctResponse")
    for i, (_, is_correct) in enumerate(choices):
        if is_correct:
            SubElement(correct, "value").text = f"CHOICE_{6000 + i}"
    outcome = SubElement(root, "outcomeDeclaration", identifier="SCORE", cardinality="single", baseType="integer")
    default = SubElement(outcome, "defaultValue")
    SubElement(default, "value").text = "0"
    body = SubElement(root, "itemBody")
    interaction = SubElement(body, "choiceInteraction", responseIdentifier="RESPONSE", maxChoices=str(sum(1 for _, c in choices if c)))
    prompt = SubElement(interaction, "prompt")
    prompt.text = question_text
    for i, (text, _) in enumerate(choices):
        choice = SubElement(interaction, "simpleChoice", identifier=f"CHOICE_{6000 + i}")
        choice.text = text
    SubElement(root, "responseProcessing", template="http://www.imsglobal.org/question/qti_v2p1/rptemplates/match_correct")
    return parseString(tostring(root, encoding="utf-8")).toprettyxml(indent="  ", encoding="UTF-8")

def generate_qti_qroc(identifier, title, question_text, choices):
    root = Element("assessmentItem", attrib={
        "xmlns": "http://www.imsglobal.org/xsd/imsqti_v2p1",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "identifier": identifier,
        "title": title,
        "adaptive": "false",
        "timeDependent": "false",
        "toolName": "Theia",
        "xsi:schemaLocation": "http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/qti/qtiv2p1/imsqti_v2p1.xsd"
    })
    response = SubElement(root, "responseDeclaration", identifier="RESPONSE", cardinality="single", baseType="string")
    correct = SubElement(response, "correctResponse")
    for val in choices:
        if val.strip():
            SubElement(correct, "value").text = val.strip()
    outcome = SubElement(root, "outcomeDeclaration", identifier="SCORE", cardinality="single", baseType="float")
    default = SubElement(outcome, "defaultValue")
    SubElement(default, "value").text = "0"
    body = SubElement(root, "itemBody")
    SubElement(body, "div").text = html.escape(question_text)
    SubElement(body, "div")
    SubElement(body[-1], "textEntryInteraction", responseIdentifier="RESPONSE", expectedLength="255")
    SubElement(root, "responseProcessing", template="http://www.imsglobal.org/question/qti_v2p1/rptemplates/match_correct")
    return parseString(tostring(root, encoding="utf-8")).toprettyxml(indent="  ", encoding="UTF-8")

def write_kfp_pool(kfp, output_dir, discipline, annee, session, titulaire, index=1):

    output_zip = f"{output_dir}/QTI_KFP_final_{index}.zip"

    kfp_title = f"{discipline}-{annee}-{session}-KFP N°{index}-{titulaire}"
    kfp_vignette = html.escape(f"<p>{kfp['vignette']}</p>")
    kfp_item_refs, kfp_files = [], []
    for idx, question in enumerate(kfp["questions"], 1):
      q_type = question["type"]
      question_text = question["question"]
      identifier = ("TEXT_QUESTION_" if q_type == "qroc" else "MULTIPLECHOICE_QUESTION_") + f"{7872730 + idx}"
      filename = identifier + ".xml"

      if q_type == "qroc":
          answers = [c[0] for c in question["choices"]]
          xml = generate_qti_qroc(identifier, "Question à Réponse Ouverte et Courte", question_text, answers)
      else:
          xml = generate_qti_qcm(identifier, "Question à réponses multiples", question_text, question["choices"])
      with open(filename, "wb") as f:
          f.write(xml)
      kfp_files.append(filename)
      kfp_item_refs.append(f'''    <assessmentItemRef identifier="{identifier}" required="true" fixed="true" href="{filename}">
      <weight identifier="WEIGHT" value="1"/>
    </assessmentItemRef>''')

    pool_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<testPart xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" identifier="DPPOOL_KFP_001" navigationMode="linear" submissionMode="individual" xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/qti/qtiv2p1/imsqti_v2p1.xsd">
  <assessmentSection identifier="DPPOOL_SECTION_KFP_001" required="false" fixed="false" title="{kfp_title}" visible="true" keepTogether="true">
    <rubricBlock view="candidate">
      <div>{kfp_vignette}</div>
    </rubricBlock>
{chr(10).join(kfp_item_refs)}
  </assessmentSection>
</testPart>'''

    with open("pool.xml", "w", encoding="utf-8") as f:
        f.write(pool_xml)
    output_zip = os.path.join(output_dir, f"KFP_N_{index}.zip")
    with zipfile.ZipFile(output_zip, "w") as zipf:
        for f in kfp_files:
            zipf.write(f, arcname=f)
            os.remove(f)
        zipf.write("pool.xml")
        os.remove("pool.xml")

    return output_zip

def run(input, output_dir, discipline, annee, session, titulaire):
    files = []
    qi_list, kfp_list = parse_docx(input)
    if qi_list:
        files.append(generate_gift(qi_list, output_dir,discipline, annee, session, titulaire))
    else:
        print("⚠️ Aucun QI détecté dans le fichier.")
    if not kfp_list:
        print("⚠️ Aucun KFP détecté dans le fichier.")
    else:
      for i, kfp in enumerate(kfp_list):
        files.append(write_kfp_pool(kfp, output_dir, discipline, annee, session, titulaire, index=i+1))
        
    return files
