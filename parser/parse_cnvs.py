import argparse
from collections import defaultdict
import csv

def chrom_key(chrom):
  chrom = chrom.lower()
  if chrom == 'x':
    chrom = 100
  elif chrom == 'y':
    chrom = 101
  elif chrom.isdigit():
    chrom = int(chrom)
  else:
    chrom = 999
  return chrom

class CopyNumberWriter(object):
  def __init__(self, cn_output_fn):
    self._cn_output_fn = cn_output_fn
    # clonal_frac represents fraction of tumor cells that are affected by CNVs,
    # *not* fraction of overall sample.
    self._keys = ('chrom', 'start', 'end', 'major_cn', 'minor_cn', 'clonal_frac')

  def _write_header(self):
    self._cn_output.write('\t'.join(self._keys) + '\n')

  def _write_cn_record(self, region):
    vals = [str(region[k]) for k in self._keys]
    self._cn_output.write('\t'.join(vals) + '\n')

  def write_cnvs(self, cn_regions):
    self._cn_output = open(self._cn_output_fn, 'w')
    self._write_header()

    chroms = sorted(cn_regions.keys(), key = chrom_key)
    for chrom in chroms:
      chrom_regions = cn_regions[chrom]
      chrom_regions.sort(key = lambda r: r['start'])
      for region in chrom_regions:
        region['chrom'] = chrom
        self._write_cn_record(region)

    self._cn_output.close()

class CnvParser(object):
  def parse(self):
    raise Exception('Not implemented')

class TitanParser(CnvParser):
  def __init__(self, titan_filename):
    self._titan_filename = titan_filename

  def parse(self):
    cn_regions = defaultdict(list)

    with open(self._titan_filename) as titanf:
      reader = csv.DictReader(titanf, delimiter='\t')
      for record in reader:
        chrom = record['Chromosome'].lower()
        cnv = {}
        cnv['start'] = int(record['Start_Position(bp)'])
        cnv['end'] = int(record['End_Position(bp)'])
        cnv['major_cn'] = int(record['MajorCN'])
        cnv['minor_cn'] = int(record['MinorCN'])

        clonal_freq = record['Clonal_Frequency']
        if clonal_freq == 'NA':
          cnv['clonal_frac'] = 1.0
        else:
          cnv['clonal_frac'] = float(clonal_freq)

        cn_regions[chrom].append(cnv)

    return cn_regions

class BattenbergParser(CnvParser):
  def __init__(self, bb_filename):
    self._bb_filename = bb_filename

  def _compute_cn(self, cnv1, cnv2):
    '''
    This code isn't used, but is retained for reference.
    '''
    cn1 = (cnv1['nmaj'] + cnv1['nmin']) * cnv1['frac']
    if cnv2:
      cn2 = (cnv2['nmaj'] + cnv2['nmin']) * cnv2['frac']
    else:
      cn2 = 0
    total_cn = cn1 + cn2
    return total_cn

  def parse(self):
    cn_regions = defaultdict(list)
    pval_threshold = 0.05

    with open(self._bb_filename) as bbf:
      header = bbf.next()
      for line in bbf:
        fields = line.strip().split()
        chrom = fields[1].lower()
        start = int(fields[2])
        end = int(fields[3])
        pval = float(fields[5])

        cnv1 = {}
        cnv1['start'] = start
        cnv1['end'] = end
        cnv1['major_cn'] = int(fields[8])
        cnv1['minor_cn'] = int(fields[9])
        cnv1['clonal_frac'] = float(fields[10])

        cnv2 = None
        # Stefan's comment on p values: The p-values correspond "to whether a
        # segment should be clonal or subclonal copynumber. We first fit a
        # clonal copynumber profile for the whole sample and then perform a
        # simple two-sided t-test twhere the null hypothesis is: A particular
        # segment is clonal. And the alternative: It is subclonal."
        #
        # Thus: if t-test falls below significance threshold, we push cnv1 to
        # clonal frequency.
        if pval <= pval_threshold:
          cnv2 = {}
          cnv2['start'] = start
          cnv2['end'] = end
          cnv2['major_cn'] = int(fields[11])
          cnv2['minor_cn'] = int(fields[12])
          cnv2['clonal_frac'] = float(fields[13])
        else:
          cnv1['clonal_frac'] = 1.0

        cn_regions[chrom].append(cnv1)
        if cnv2 is not None:
          cn_regions[chrom].append(cnv2)
    return cn_regions

def main():
  parser = argparse.ArgumentParser(
    description='Create CNV input file for parser from Battenberg or TITAN data',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
  )
  parser.add_argument('-f', '--cnv-format', dest='input_type', required=True, choices=('battenberg', 'titan'),
    help='Type of CNV input')
  parser.add_argument('--cnv-output', dest='cnv_output_filename', default='cnvs.txt',
    help='Output destination for parsed CNVs')
  parser.add_argument('cnv_file')
  args = parser.parse_args()

  if args.input_type == 'battenberg':
    parser = BattenbergParser(args.cnv_file)
  elif args.input_type == 'titan':
    parser = TitanParser(args.cnv_file)
  else:
    raise Exception('Unknown input type')

  writer = CopyNumberWriter(args.cnv_output_filename)
  regions = parser.parse()
  writer.write_cnvs(regions)

if __name__ == '__main__':
  main()
