"""
Routines to read in association file between genes and GO terms.
"""

__copyright__ = "Copyright (C) 2010-2019, H Tang et al. All rights reserved."
__author__ = "various"

from collections import defaultdict
import os
import sys
#### import wget
#### import requests
#### from ftplib import FTP
from goatools.base import dnld_file
from goatools.base import ftp_get
from goatools.anno.factory import get_objanno
from goatools.anno.factory import get_anno_desc
#### from goatools.base import wget
from goatools.semantic import TermCounts
from goatools.anno.gaf_reader import GafReader
from goatools.anno.genetogo_reader import Gene2GoReader
from goatools.anno.opts import AnnoOptions

def dnld_assc(assc_name, go2obj=None, prt=sys.stdout):
    """Download association from http://geneontology.org/gene-associations."""
    # Example assc_name: "tair.gaf"
    # Download the Association
    dirloc, assc_base = os.path.split(assc_name)
    if not dirloc:
        dirloc = os.getcwd()
    assc_locfile = os.path.join(dirloc, assc_base) if not dirloc else assc_name
    if not os.path.isfile(assc_locfile):
        # assc_http = "http://geneontology.org/gene-associations/"
        assc_http = "http://current.geneontology.org/annotations/"
        for ext in ['gz']:
            src = os.path.join(assc_http, "{ASSC}.{EXT}".format(ASSC=assc_base, EXT=ext))
            dnld_file(src, assc_locfile, prt, loading_bar=None)
    # Read the downloaded association
    assc_orig = read_gaf(assc_locfile, prt)
    if go2obj is None:
        return assc_orig
    # If a GO DAG is provided, use only GO IDs present in the GO DAG
    assc = {}
    goids_dag = set(go2obj.keys())
    for gene, goids_cur in assc_orig.items():
        assc[gene] = goids_cur.intersection(goids_dag)
    return assc

def read_associations(assoc_fn, anno_type='id2gos', **kws):
    """Return associatinos in id2gos format"""
    # kws get_objanno: taxids hdr_only prt allow_missing_symbol
    obj = get_objanno(assoc_fn, anno_type, **kws)
    # kws get_id2gos: evidence_set keep_ND keep_NOT b_geneid2gos go2geneids
    return obj.get_id2gos(**kws)

def get_assoc_ncbi_taxids(taxids, force_dnld=False, loading_bar=True, **kws):
    """Download NCBI's gene2go. Return annotations for user-specified taxid(s)."""
    fin = kws['gene2go'] if 'gene2go' in kws else os.path.join(os.getcwd(), "gene2go")
    dnld_ncbi_gene_file(fin, force_dnld, loading_bar=loading_bar)
    return read_ncbi_gene2go(fin, taxids, **kws)

def dnld_ncbi_gene_file(fin, force_dnld=False, log=sys.stdout, loading_bar=True):
    """Download a file from NCBI Gene's ftp server."""
    if not os.path.exists(fin) or force_dnld:
        import gzip
        fin_dir, fin_base = os.path.split(fin)
        fin_gz = "{F}.gz".format(F=fin_base)
        fin_gz = os.path.join(fin_dir, fin_gz)
        if os.path.exists(fin_gz):
            os.remove(fin_gz)
        fin_ftp = "ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/{F}.gz".format(F=fin_base)
        ## if log is not None:
        ##     log.write("  DOWNLOADING GZIP: {GZ}\n".format(GZ=fin_ftp))
        ## if loading_bar:
        ##     loading_bar = wget.bar_adaptive
        ## wget.download(fin_ftp, bar=loading_bar)
        ## rsp = wget(fin_ftp)
        ftp_get(fin_ftp, fin_gz)
        with gzip.open(fin_gz, 'rb') as zstrm:
            if log is not None:
                log.write("\n  READ GZIP:  {F}\n".format(F=fin_gz))
            with open(fin, 'wb') as ostrm:
                ostrm.write(zstrm.read())
                if log is not None:
                    log.write("  WROTE UNZIPPED: {F}\n".format(F=fin))

def dnld_annofile(fin_anno, anno_type):
    """Download annotation file, if needed"""
    if os.path.exists(fin_anno):
        return
    anno_type = get_anno_desc(fin_anno, anno_type)
    if anno_type == 'gene2go':
        ### download_ncbi_associations(fin_anno)
        dnld_ncbi_gene_file(fin_anno)
    if anno_type in {'gaf', 'gpad'}:
        dnld_assc(fin_anno)

def read_ncbi_gene2go(fin_gene2go, taxids=None, **kws):
    """Read NCBI's gene2go. Return gene2go data for user-specified taxids."""
    obj = Gene2GoReader(fin_gene2go, taxids)
    # b_geneid2gos = not kws.get('go2geneids', False)
    opt = AnnoOptions(**kws)
    # By default, return id2gos. User can cause go2geneids to be returned by:
    #   >>> read_ncbi_gene2go(..., go2geneids=True
    if 'taxid2asscs' not in kws:
        if len(obj.taxid2asscs) == 1:
            taxid = next(iter(obj.taxid2asscs))
            return obj.get_annotations_dct(taxid, opt)
    # Optional detailed associations split by taxid and having both ID2GOs & GO2IDs
    # e.g., taxid2asscs = defaultdict(lambda: defaultdict(lambda: defaultdict(set))
    t2asscs_ret = obj.get_annotations_taxid2dct(opt)
    t2asscs_usr = kws.get('taxid2asscs', defaultdict(lambda: defaultdict(lambda: defaultdict(set))))
    if 'taxid2asscs' in kws:
        obj.fill_taxid2asscs(t2asscs_usr, t2asscs_ret)
    return obj.get_id2gos_all(t2asscs_ret)

def read_ncbi_gene2go_old(fin_gene2go, taxids=None, **kws):
    """Read NCBI's gene2go. Return gene2go data for user-specified taxids."""
    # kws: taxid2asscs evidence_set
    # Simple associations
    id2gos = defaultdict(set)
    # Optional detailed associations split by taxid and having both ID2GOs & GO2IDs
    # e.g., taxid2asscs = defaultdict(lambda: defaultdict(lambda: defaultdict(set))
    taxid2asscs = kws.get('taxid2asscs', None)
    evs = kws.get('evidence_set', None)
    # By default, return id2gos. User can cause go2geneids to be returned by:
    #   >>> read_ncbi_gene2go(..., go2geneids=True
    b_geneid2gos = not kws.get('go2geneids', False)
    if taxids is None: # Default taxid is Human
        taxids = [9606]
    with open(fin_gene2go) as ifstrm:
        # pylint: disable=too-many-nested-blocks
        for line in ifstrm:
            if line[0] != '#': # Line contains data. Not a comment
                line = line.rstrip() # chomp
                flds = line.split('\t')
                if len(flds) >= 5:
                    taxid_curr, geneid, go_id, evidence, qualifier = flds[:5]
                    taxid_curr = int(taxid_curr)
                    # NOT: Used when gene is expected to have function F, but does NOT.
                    # ND : GO function not seen after exhaustive annotation attempts to the gene.
                    if taxid_curr in taxids and qualifier != 'NOT' and evidence != 'ND':
                        # Optionally specify a subset of GOs based on their evidence.
                        if evs is None or evidence in evs:
                            geneid = int(geneid)
                            if b_geneid2gos:
                                id2gos[geneid].add(go_id)
                            else:
                                id2gos[go_id].add(geneid)
                            if taxid2asscs is not None:
                                taxid2asscs[taxid_curr]['ID2GOs'][geneid].add(go_id)
                                taxid2asscs[taxid_curr]['GO2IDs'][go_id].add(geneid)
        sys.stdout.write("  {N:,} items READ: {ASSC}\n".format(N=len(id2gos), ASSC=fin_gene2go))
    return id2gos # return simple associations

def get_gaf_hdr(fin_gaf):
    """Read Gene Association File (GAF). Return GAF version and data info."""
    return GafReader(fin_gaf, hdr_only=True).hdr

def read_gaf(fin_gaf, prt=sys.stdout, hdr_only=False, allow_missing_symbol=False, **kws):
    """Read Gene Association File (GAF). Return data."""
    # keyword arguments what is read from GAF.
    hdr_only = kws.get('hdr_only', None) # Read all data from GAF by default
    # Read GAF file
    gafobj = GafReader(fin_gaf, hdr_only, prt, allow_missing_symbol)
    return gafobj.read_gaf(**kws)

def get_b2aset(a2bset):
    """Given gene2gos, return go2genes. Given go2genes, return gene2gos."""
    b2aset = {}
    for a_item, bset in a2bset.items():
        for b_item in bset:
            if b_item in b2aset:
                b2aset[b_item].add(a_item)
            else:
                b2aset[b_item] = set([a_item])
    return b2aset

def get_assc_pruned(assc_geneid2gos, min_genecnt=None, max_genecnt=None, prt=sys.stdout):
    """Remove GO IDs associated with large numbers of genes. Used in stochastic simulations."""
    # DEFN WAS: get_assc_pruned(assc_geneid2gos, max_genecnt=None, prt=sys.stdout):
    #      ADDED min_genecnt argument and functionality
    if max_genecnt is None and min_genecnt is None:
        return assc_geneid2gos, set()
    go2genes_orig = get_b2aset(assc_geneid2gos)
    # go2genes_prun = {go:gs for go, gs in go2genes_orig.items() if len(gs) <= max_genecnt}
    go2genes_prun = {}
    for goid, genes in go2genes_orig.items():
        num_genes = len(genes)
        if (min_genecnt is None or num_genes >= min_genecnt) and \
           (max_genecnt is None or num_genes <= max_genecnt):
            go2genes_prun[goid] = genes
    num_was = len(go2genes_orig)
    num_now = len(go2genes_prun)
    gos_rm = set(go2genes_orig.keys()).difference(set(go2genes_prun.keys()))
    assert num_was-num_now == len(gos_rm)
    if prt is not None:
        if min_genecnt is None:
            min_genecnt = 1
        if max_genecnt is None:
            max_genecnt = "Max"
        prt.write("{N:4} GO IDs pruned. Kept {NOW} GOs assc w/({m} to {M} genes)\n".format(
            m=min_genecnt, M=max_genecnt, N=num_was-num_now, NOW=num_now))
    return get_b2aset(go2genes_prun), gos_rm

def read_annotations(**kws):
    """Read annotations from either a GAF file or NCBI's gene2go file."""
    if 'gaf' not in kws and 'gene2go' not in kws:
        return
    gene2gos = None
    if 'gaf' in kws:
        gene2gos = read_gaf(kws['gaf'], prt=sys.stdout)
        if not gene2gos:
            raise RuntimeError("NO ASSOCIATIONS LOADED FROM {F}".format(F=kws['gaf']))
    elif 'gene2go' in kws:
        assert 'taxid' in kws, 'taxid IS REQUIRED WHEN READING gene2go'
        gene2gos = read_ncbi_gene2go(kws['gene2go'], taxids=[kws['taxid']])
        if not gene2gos:
            raise RuntimeError("NO ASSOCIATIONS LOADED FROM {F} FOR TAXID({T})".format(
                F=kws['gene2go'], T=kws['taxid']))
    return gene2gos

def get_tcntobj(go2obj, **kws):
    """Return a TermCounts object if the user provides an annotation file, otherwise None."""
    # kws: gaf gene2go
    annots = read_annotations(**kws)
    if annots:
        return TermCounts(go2obj, annots)


# Copyright (C) 2010-2019, H Tang et al. All rights reserved."
