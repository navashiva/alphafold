import gradio as gr
from datetime import datetime
import os
import subprocess
import zipfile
from absl import logging

logging.set_verbosity(logging.INFO)

OUTPUT_DIR=os.getenv("OUTPUT_DIR")
DATA_DIR=os.getenv("DATA_DIR")

def make_zipfile(output_filename, source_dir):
    relroot = os.path.abspath(os.path.join(source_dir, os.pardir))
    with zipfile.ZipFile(f'{OUTPUT_DIR}/{output_filename}.zip', "w", zipfile.ZIP_DEFLATED) as zip:
        for root, dirs, files in os.walk(source_dir):
            # add directory (needed for empty dirs)
            zip.write(root, os.path.relpath(root, relroot))
            for file in files:
                filename = os.path.join(root, file)
                if os.path.isfile(filename): # regular files only
                    arcname = os.path.join(os.path.relpath(root, relroot), file)
                    zip.write(filename, arcname)
        zip.close()
    return f'{OUTPUT_DIR}/{output_filename}.zip'

def alphafold_predict(fasta_paths, model_preset, db_preset, max_template_date):
    command_args = []

    command_args.append(f'--fasta_paths={fasta_paths.name}')

    # Path to the Uniref90 database for use by JackHMMER.
    uniref90_database_path = os.path.join(
        DATA_DIR, 'uniref90', 'uniref90.fasta')

    # Path to the Uniprot database for use by JackHMMER.
    uniprot_database_path = os.path.join(
        DATA_DIR, 'uniprot', 'uniprot.fasta')

    # Path to the MGnify database for use by JackHMMER.
    mgnify_database_path = os.path.join(
        DATA_DIR, 'mgnify', 'mgy_clusters_2018_12.fa')

    # Path to the BFD database for use by HHblits.
    bfd_database_path = os.path.join(
        DATA_DIR, 'bfd',
        'bfd_metaclust_clu_complete_id30_c90_final_seq.sorted_opt')

    # Path to the Small BFD database for use by JackHMMER.
    small_bfd_database_path = os.path.join(
        DATA_DIR, 'small_bfd', 'bfd-first_non_consensus_sequences.fasta')

    # Path to the Uniclust30 database for use by HHblits.
    uniclust30_database_path = os.path.join(
        DATA_DIR, 'uniclust30', 'uniclust30_2018_08', 'uniclust30_2018_08')

    # Path to the PDB70 database for use by HHsearch.
    pdb70_database_path = os.path.join(DATA_DIR, 'pdb70', 'pdb70')

    # Path to the PDB seqres database for use by hmmsearch.
    pdb_seqres_database_path = os.path.join(
        DATA_DIR, 'pdb_seqres', 'pdb_seqres.txt')

    # Path to a directory with template mmCIF structures, each named <pdb_id>.cif.
    template_mmcif_dir = os.path.join(DATA_DIR, 'pdb_mmcif', 'mmcif_files')

    # Path to a file mapping obsolete PDB IDs to their replacements.
    obsolete_pdbs_path = os.path.join(DATA_DIR, 'pdb_mmcif', 'obsolete.dat')


    database_paths = [
        ('uniref90_database_path', uniref90_database_path),
        ('mgnify_database_path', mgnify_database_path),
        ('data_dir', DATA_DIR),
        ('template_mmcif_dir', template_mmcif_dir),
        ('obsolete_pdbs_path', obsolete_pdbs_path),
    ]

    if model_preset == 'multimer':
        database_paths.append(('uniprot_database_path', uniprot_database_path))
        database_paths.append(('pdb_seqres_database_path',
                               pdb_seqres_database_path))
    else:
        database_paths.append(('pdb70_database_path', pdb70_database_path))

    if db_preset == 'reduced_dbs':
        database_paths.append(('small_bfd_database_path', small_bfd_database_path))
    else:
        database_paths.extend([
            ('uniclust30_database_path', uniclust30_database_path),
            ('bfd_database_path', bfd_database_path),
        ])
    for name, path in database_paths:
        if path:
            command_args.append(f'--{name}={path}')

    if max_template_date:
        command_args.append(f'--max_template_date={max_template_date}')

    command_args.extend([
        f'--output_dir={OUTPUT_DIR}',
        f'--model_preset={model_preset}',
        f'--db_preset={db_preset}',
        f'--data_dir={DATA_DIR}',
        '--logtostderr',
    ])

    run_alphafold=['python', '/app/alphafold/run_alphafold.py']
    run_alphafold.extend(command_args)

    logging.info(run_alphafold)
    process = subprocess.Popen(run_alphafold,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               universal_newlines=True)

    while True:
        output = process.stdout.readline()
        print(output.strip())
        # Do something else
        return_code = process.poll()
        if return_code is not None:
            print('RETURN CODE', return_code)
            # Process has finished, read rest of the output
            for output in process.stdout.readlines():
                print(output.strip())
            break
    predict_dir_name = (fasta_paths.name).split('/')[-1].split('.')[0]
    targetFile = make_zipfile(predict_dir_name,f'{OUTPUT_DIR}/{predict_dir_name}')
    if 'frontend' in targetFile:
        targetFile = targetFile.split('frontend')[-1]
    html = f'<div style="max-width:100%; max-height:360px; overflow:auto"><a href="{targetFile}" download="{predict_dir_name}.zip"><img src="/static/media/zip_icon.jpg" alt="{predict_dir_name}.zip" class="center"></a></div>'
    return html

gr.Interface(fn=alphafold_predict,
             inputs=[
                 gr.inputs.File(file_count="single", type="file", label="FASTA file object", optional=True),
                 gr.inputs.Radio(['monomer', 'monomer_casp14', 'monomer_ptm', 'multimer'], type="value",
                                 default="monomer", label="Preset model"),
                 gr.inputs.Radio(['full_dbs', 'reduced_dbs'], type="value",
                                 default="full_dbs", label="Database model"),
                 gr.inputs.Textbox(lines=1, placeholder="2020-05-14", default=datetime.now().strftime("%Y-%m-%d"),
                                   label="Maximum template release date to consider")
             ], outputs="html").launch(inline=False, inbrowser=False, share=False, debug=True, server_name="0.0.0.0",
                                       server_port=8080, enable_queue=True)