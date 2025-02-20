# -*- coding: utf-8 -*-

import os
import glob
import sys
import unittest
import pysam
import shutil
import gzip

try:
    from pathlib import Path
except ImportError:
    Path = None

from TestUtils import get_temp_filename, check_lines_equal, load_and_convert, make_data_files, CBCF_DATADIR, get_temp_context


def setUpModule():
    make_data_files(CBCF_DATADIR)


def read_header(filename):
    data = []
    if filename.endswith(".gz"):
        for line in gzip.open(filename):
            line = line.decode("ascii")
            if line.startswith("#"):
                data.append(line)
    else:
        with open(filename) as f:
            for line in f:
                if line.startswith("#"):
                    data.append(line)

    return data


def read_index_header(filename):
    with gzip.open(filename) as infile:
        magic = infile.read(4)
    return magic


class TestMissingGenotypes(unittest.TestCase):

    filename = "missing_genotypes.vcf"

    def setUp(self):
        self.compare = load_and_convert(
            os.path.join(CBCF_DATADIR, self.filename),
            encode=False)

    def check(self, filename):
        """see issue 203 - check for segmentation fault"""
        fn = os.path.join(CBCF_DATADIR, filename)
        self.assertEqual(True, os.path.exists(fn))
        v = pysam.VariantFile(fn)
        for site in v:
            for ss, rec in site.samples.items():
                a, b = ss, rec

        v = pysam.VariantFile(fn)
        for x, site in enumerate(v):
            for ss, rec in site.samples.items():
                a, b = ss, rec.alleles
                a, b = ss, rec.allele_indices

    def testVCF(self):
        self.check(self.filename)

    def testVCFGZ(self):
        self.check(self.filename + ".gz")


class TestMissingSamples(unittest.TestCase):

    filename = "gnomad.vcf"

    def setUp(self):
        self.compare = load_and_convert(
            os.path.join(CBCF_DATADIR, self.filename),
            encode=False)

    def check(self, filename):
        """see issue #593"""
        fn = os.path.join(CBCF_DATADIR, filename)
        self.assertEqual(True, os.path.exists(fn))
        expect_fail = not "fixed" in self.filename
        with pysam.VariantFile(fn) as inf:
            rec = next(inf.fetch())
            if expect_fail:
                self.assertRaises(ValueError, rec.info.__getitem__, "GC")
            else:
                self.assertEqual(rec.info["GC"], (27, 35, 16))

    def testVCF(self):
        self.check(self.filename)

    def testVCFGZ(self):
        self.check(self.filename + ".gz")


class TestMissingSamplesFixed(TestMissingSamples):
    # workaround for NUMBER=G in INFO records:
    # perl 's/Number=G/Number=./ if (/INFO/)'
    
    filename = "gnomad_fixed.vcf"


class TestOpening(unittest.TestCase):

    def testMissingFile(self):
        self.assertRaises(IOError, pysam.VariantFile,
                          "missing_file.vcf")

    def testMissingFileVCFGZ(self):
        self.assertRaises(IOError, pysam.VariantFile,
                          "missing_file.vcf.gz")

    def testEmptyFileVCF(self):
        with get_temp_context("tmp_testEmptyFile.vcf") as fn:
            with open(fn, "w"):
                pass
            self.assertRaises(ValueError, pysam.VariantFile, fn)

    if Path and sys.version_info >= (3, 6):
        def testEmptyFileVCFFromPath(self):
            with get_temp_context("tmp_testEmptyFile.vcf") as fn:
                with open(fn, "w"):
                    pass
                self.assertRaises(ValueError, pysam.VariantFile,
                                  Path(fn))

    def testEmptyFileVCFGZWithIndex(self):
        with get_temp_context("tmp_testEmptyFile.vcf") as fn:
            with open(fn, "w"):
                pass
            # tabix_index will automatically compress
            pysam.tabix_index(fn,
                              preset="vcf",
                              force=True)

            self.assertRaises(ValueError, pysam.VariantFile, fn + ".gz")

    def testEmptyFileVCFGZWithoutIndex(self):
        with get_temp_context("tmp_testEmptyFileWithoutIndex.vcf") as fn:
            with open(fn, "w"):
                pass

            pysam.tabix_compress(fn,
                                 fn + ".gz",
                                 force=True)

            self.assertRaises(ValueError, pysam.VariantFile, fn + ".gz")

    def testEmptyFileVCFOnlyHeader(self):
        with pysam.VariantFile(os.path.join(
                CBCF_DATADIR,
                "example_vcf42_only_header.vcf")) as inf:
            self.assertEqual(len(list(inf.fetch())), 0)

    def testEmptyFileVCFGZOnlyHeader(self):
        with pysam.VariantFile(os.path.join(
                CBCF_DATADIR,
                "example_vcf42_only_header.vcf")) as inf:
            self.assertEqual(len(list(inf.fetch())), 0)

    def testDetectVCF(self):
        with pysam.VariantFile(os.path.join(CBCF_DATADIR,
                                            "example_vcf40.vcf")) as inf:
            self.assertEqual(inf.category, 'VARIANTS')
            self.assertEqual(inf.format, 'VCF')
            self.assertEqual(inf.compression, 'NONE')
            self.assertFalse(inf.is_remote)
            self.assertFalse(inf.is_stream)
            self.assertEqual(len(list(inf.fetch())), 5)

    def testDetectVCFGZ(self):
        with pysam.VariantFile(os.path.join(CBCF_DATADIR,
                                            "example_vcf40.vcf.gz")) as inf:
            self.assertEqual(inf.category, 'VARIANTS')
            self.assertEqual(inf.format, 'VCF')
            self.assertEqual(inf.compression, 'BGZF')
            self.assertFalse(inf.is_remote)
            self.assertFalse(inf.is_stream)
            self.assertEqual(len(list(inf.fetch())), 5)

    def testDetectBCF(self):
        with pysam.VariantFile(os.path.join(
                CBCF_DATADIR,
                "example_vcf40.bcf")) as inf:
            self.assertEqual(inf.category, 'VARIANTS')
            self.assertEqual(inf.format, 'BCF')
            self.assertEqual(inf.compression, 'BGZF')
            self.assertFalse(inf.is_remote)
            self.assertFalse(inf.is_stream)
            self.assertEqual(len(list(inf.fetch())), 5)


class TestIndexFormatsVCF(unittest.TestCase):

    vcf_filename = os.path.join(CBCF_DATADIR, "example_vcf40.vcf")
    bcf_filename = os.path.join(CBCF_DATADIR, "example_vcf40.bcf")
    
    def test_vcf_with_tbi_index(self):
        with get_temp_context("tmp_fn.vcf") as fn:
            shutil.copyfile(self.vcf_filename, fn)
            pysam.tabix_index(fn, preset="vcf", force=True)
            self.assertTrue(os.path.exists(fn + ".gz" + ".tbi"))
            self.assertEqual(read_index_header(fn + ".gz.tbi"), b"TBI\1")
            self.assertFalse(os.path.exists(fn + ".gz" + ".csi"))
            
            with pysam.VariantFile(fn + ".gz") as inf:
                self.assertEqual(len(list(inf.fetch("20"))), 3)

    def test_vcf_with_csi_index(self):
        with get_temp_context("tmp_fn.vcf") as fn:
            shutil.copyfile(self.vcf_filename, fn)

            pysam.tabix_index(fn, preset="vcf", force=True, csi=True)
            self.assertTrue(os.path.exists(fn + ".gz" + ".csi"))
            self.assertEqual(read_index_header(fn + ".gz.csi"), b"CSI\1")
            self.assertFalse(os.path.exists(fn + ".gz" + ".tbi"))
            
            with pysam.VariantFile(fn + ".gz") as inf:
                self.assertEqual(len(list(inf.fetch("20"))), 3)

    def test_bcf_with_prebuilt_csi(self):
        with get_temp_context("tmp_fn.bcf") as fn:
            shutil.copyfile(self.bcf_filename, fn)
            shutil.copyfile(self.bcf_filename + ".csi", fn + ".csi")

            self.assertTrue(os.path.exists(fn + ".csi"))
            self.assertEqual(read_index_header(fn + ".csi"), b"CSI\1")
            self.assertFalse(os.path.exists(fn + ".tbi"))
            
            with pysam.VariantFile(fn) as inf:
                self.assertEqual(len(list(inf.fetch("20"))), 3)

    def test_bcf_with_tbi_index_will_produce_csi(self):
        with get_temp_context("tmp_fn.bcf") as fn:
            shutil.copyfile(self.bcf_filename, fn)

            pysam.tabix_index(fn, preset="bcf", force=True, csi=False)
            self.assertTrue(os.path.exists(fn + ".csi"))
            self.assertEqual(read_index_header(fn + ".csi"), b"CSI\1")
            self.assertFalse(os.path.exists(fn + ".tbi"))
            
            with pysam.VariantFile(fn) as inf:
                self.assertEqual(len(list(inf.fetch("20"))), 3)

    def test_bcf_with_csi_index(self):
        with get_temp_context("tmp_fn.bcf") as fn:
            shutil.copyfile(self.bcf_filename, fn)

            pysam.tabix_index(fn, preset="vcf", force=True, csi=True)
            
            self.assertTrue(os.path.exists(fn + ".csi"))
            self.assertEqual(read_index_header(fn + ".csi"), b"CSI\1")
            self.assertFalse(os.path.exists(fn + ".tbi"))
            
            with pysam.VariantFile(fn) as inf:
                self.assertEqual(len(list(inf.fetch("20"))), 3)


class TestHeader(unittest.TestCase):

    filename = "example_vcf40.vcf"

    def testStr(self):

        fn = os.path.join(CBCF_DATADIR, self.filename)
        v = pysam.VariantFile(fn)

        ref = read_header(fn)
        comp = str(v.header).splitlines(True)

        self.assertEqual(sorted(ref),
                         sorted(comp))

    def testIterator(self):

        fn = os.path.join(CBCF_DATADIR, self.filename)
        v = pysam.VariantFile(fn)

        ref = read_header(fn)
        # remove last header line starting with #CHROM
        ref.pop()
        ref = sorted(ref)
        comp = sorted(str(x) for x in v.header.records)

        self.assertEqual(len(ref), len(comp))

        for x, y in zip(ref, comp):
            self.assertEqual(x, y)


# These tests need to be separate and start from newly opened files.  This
# is because htslib's parser is lazy and the pysam API needs to trigger
# appropriate parsing when accessing each time of data.  Failure to do so
# will result in crashes or return of incorrect data.  Thus this test suite
# is testing both the triggering of the lazy parser and the results of the
# parser.
class TestParsing(unittest.TestCase):

    filename = "example_vcf40.vcf.gz"

    def testChrom(self):
        fn = os.path.join(CBCF_DATADIR, self.filename)
        v = pysam.VariantFile(fn)
        chrom = [rec.chrom for rec in v]
        self.assertEqual(chrom, ['M', '17', '20', '20', '20'])

    if Path and sys.version_info >= (3, 6):
        def testChromFromPath(self):
            fn = os.path.join(CBCF_DATADIR, self.filename)
            v = pysam.VariantFile(Path(fn))
            chrom = [rec.chrom for rec in v]
            self.assertEqual(chrom, ['M', '17', '20', '20', '20'])

    def testPos(self):
        fn = os.path.join(CBCF_DATADIR, self.filename)
        v = pysam.VariantFile(fn)
        pos = [rec.pos for rec in v]
        self.assertEqual(pos, [1230237, 14370, 17330, 1110696, 1234567])

    def testStart(self):
        fn = os.path.join(CBCF_DATADIR, self.filename)
        v = pysam.VariantFile(fn)
        start = [rec.start for rec in v]
        self.assertEqual(start, [1230236, 14369, 17329, 1110695, 1234566])

    def testStop(self):
        fn = os.path.join(CBCF_DATADIR, self.filename)
        v = pysam.VariantFile(fn)
        stop = [rec.stop for rec in v]
        self.assertEqual(stop, [1230237, 14370, 17330, 1110696, 1234570])

    def testId(self):
        fn = os.path.join(CBCF_DATADIR, self.filename)
        v = pysam.VariantFile(fn)
        ids = [rec.id for rec in v]
        self.assertEqual(
            ids, [None, 'rs6054257', None, 'rs6040355', 'microsat1'])

    def testRef(self):
        fn = os.path.join(CBCF_DATADIR, self.filename)
        v = pysam.VariantFile(fn)
        ref = [rec.ref for rec in v]
        self.assertEqual(ref, ['T', 'G', 'T', 'A', 'GTCT'])

    def testAlt(self):
        fn = os.path.join(CBCF_DATADIR, self.filename)
        v = pysam.VariantFile(fn)
        alts = [rec.alts for rec in v]
        self.assertEqual(alts, [None, ('A',), ('A',),
                                ('G', 'T'), ('G', 'GTACT')])

    def testAlleles(self):
        fn = os.path.join(CBCF_DATADIR, self.filename)
        v = pysam.VariantFile(fn)
        alleles = [rec.alleles for rec in v]
        self.assertEqual(alleles, [
                         ('T',), ('G', 'A'), ('T', 'A'), ('A', 'G', 'T'), ('GTCT', 'G', 'GTACT')])

    def testQual(self):
        fn = os.path.join(CBCF_DATADIR, self.filename)
        v = pysam.VariantFile(fn)
        qual = [rec.qual for rec in v]
        self.assertEqual(qual, [47.0, 29.0, 3.0, 67.0, 50.0])

    def testFilter(self):
        fn = os.path.join(CBCF_DATADIR, self.filename)
        v = pysam.VariantFile(fn)
        filter = [rec.filter.keys() for rec in v]
        self.assertEqual(filter, [['PASS'], ['PASS'],
                                  ['q10'], ['PASS'], ['PASS']])

    def testInfo(self):
        fn = os.path.join(CBCF_DATADIR, self.filename)
        v = pysam.VariantFile(fn)
        info = [rec.info.items() for rec in v]
        self.assertEqual(info, [[('NS', 3), ('DP', 13), ('AA', 'T')],
                                [('NS', 3), ('DP', 14), ('AF', (0.5,)),
                                 ('DB', True), ('H2', True)],
                                [('NS', 3), ('DP', 11),
                                 ('AF', (0.017000000923871994,))],
                                [('NS', 2), ('DP', 10), ('AF', (0.3330000042915344, 0.6669999957084656)),
                                 ('AA', 'T'), ('DB', True)],
                                [('NS', 3), ('DP', 9), ('AA', 'G')]])

    def testFormat(self):
        fn = os.path.join(CBCF_DATADIR, self.filename)
        v = pysam.VariantFile(fn)
        format = [rec.format.keys() for rec in v]
        self.assertEqual(format, [['GT', 'GQ', 'DP', 'HQ'],
                                  ['GT', 'GQ', 'DP', 'HQ'],
                                  ['GT', 'GQ', 'DP', 'HQ'],
                                  ['GT', 'GQ', 'DP', 'HQ'],
                                  ['GT', 'GQ', 'DP']])

    def testSampleAlleles(self):
        fn = os.path.join(CBCF_DATADIR, self.filename)
        v = pysam.VariantFile(fn)
        alleles = [s.alleles for rec in v for s in rec.samples.values()]
        self.assertEqual(alleles, [('T', 'T'), ('T', 'T'), ('T', 'T'),
                                   ('G', 'G'), ('A', 'G'), ('A', 'A'),
                                   ('T', 'T'), ('T', 'A'), ('T', 'T'),
                                   ('G', 'T'), ('T', 'G'), ('T', 'T'),
                                   ('GTCT', 'G'), ('GTCT', 'GTACT'),
                                   ('G', 'G')])

    def testSampleFormats(self):
        fn = os.path.join(CBCF_DATADIR, self.filename)
        v = pysam.VariantFile(fn)
        format = [s.items() for rec in v for s in rec.samples.values()]
        self.assertEqual(format, [[('GT', (0, 0)), ('GQ', 54), ('DP', 7), ('HQ', (56, 60))],
                                  [('GT', (0, 0)), ('GQ', 48),
                                   ('DP', 4), ('HQ', (51, 51))],
                                  [('GT', (0, 0)), ('GQ', 61),
                                   ('DP', 2), ('HQ', (None,))],
                                  [('GT', (0, 0)), ('GQ', 48),
                                   ('DP', 1), ('HQ', (51, 51))],
                                  [('GT', (1, 0)), ('GQ', 48),
                                   ('DP', 8), ('HQ', (51, 51))],
                                  [('GT', (1, 1)), ('GQ', 43),
                                   ('DP', 5), ('HQ', (None, None))],
                                  [('GT', (0, 0)), ('GQ', 49),
                                   ('DP', 3), ('HQ', (58, 50))],
                                  [('GT', (0, 1)), ('GQ', 3),
                                   ('DP', 5), ('HQ', (65, 3))],
                                  [('GT', (0, 0)), ('GQ', 41),
                                   ('DP', 3), ('HQ', (None,))],
                                  [('GT', (1, 2)), ('GQ', 21),
                                   ('DP', 6), ('HQ', (23, 27))],
                                  [('GT', (2, 1)), ('GQ', 2),
                                   ('DP', 0), ('HQ', (18, 2))],
                                  [('GT', (2, 2)), ('GQ', 35),
                                   ('DP', 4), ('HQ', (None,))],
                                  [('GT', (0, 1)), ('GQ', 35), ('DP', 4)],
                                  [('GT', (0, 2)), ('GQ', 17), ('DP', 2)],
                                  [('GT', (1, 1)), ('GQ', 40), ('DP', 3)]])

    def testSampleAlleleIndices(self):
        fn = os.path.join(CBCF_DATADIR, self.filename)
        v = pysam.VariantFile(fn)
        indices = [s.allele_indices for rec in v for s in rec.samples.values()]
        self.assertEqual(indices, [(0, 0), (0, 0), (0, 0), (0, 0), (1, 0),
                                   (1, 1), (0, 0), (0, 1), (0, 0), (1, 2),
                                   (2, 1), (2, 2), (0, 1), (0, 2), (1, 1)])


class TestIndexFilename(unittest.TestCase):

    filenames = [('example_vcf40.vcf.gz', 'example_vcf40.vcf.gz.tbi'),
                 ('example_vcf40.vcf.gz', 'example_vcf40.vcf.gz.csi'),
                 ('example_vcf40.bcf', 'example_vcf40.bcf.csi')]

    def testOpen(self):
        for fn, idx_fn in self.filenames:
            fn = os.path.join(CBCF_DATADIR, fn)
            idx_fn = os.path.join(CBCF_DATADIR, idx_fn)

            with pysam.VariantFile(fn, index_filename=idx_fn) as inf:
                self.assertEqual(len(list(inf.fetch('20'))), 3)


class TestConstructionVCFWithContigs(unittest.TestCase):
    """construct VariantFile from scratch."""

    filename = "example_vcf42_withcontigs.vcf"
    compression = 'NONE'
    description = 'VCF version 4.2 variant calling text'

    def testBase(self):
        with pysam.VariantFile(os.path.join(CBCF_DATADIR, self.filename)) as inf:
            self.assertEqual(inf.category, 'VARIANTS')
            self.assertEqual(inf.format, 'VCF')
            self.assertEqual(inf.version, (4, 2))
            self.assertEqual(inf.compression, self.compression)
            self.assertEqual(inf.description, self.description)
            self.assertTrue(inf.is_open)
            self.assertEqual(inf.is_read, True)
            self.assertEqual(inf.is_write, False)

    def complete_check(self, fn_in, fn_out):
        self.maxDiff = None
        check_lines_equal(
            self, fn_in, fn_out, sort=True,
            filter_f=lambda x: x.startswith("##contig"))
        os.unlink(fn_out)

    def testConstructionWithRecords(self):

        fn_in = os.path.join(CBCF_DATADIR, self.filename)
        fn_out = get_temp_filename(suffix=".vcf")
        vcf_in = pysam.VariantFile(fn_in)

        header = pysam.VariantHeader()

        for record in vcf_in.header.records:
            header.add_record(record)

        for sample in vcf_in.header.samples:
            header.add_sample(sample)

        vcf_out = pysam.VariantFile(fn_out, "w", header=header)
        for record in vcf_in:
            record.translate(header)
            vcf_out.write(record)

        vcf_in.close()
        vcf_out.close()
        self.complete_check(fn_in, fn_out)

    def testConstructionFromCopy(self):

        fn_in = os.path.join(CBCF_DATADIR, self.filename)
        fn_out = get_temp_filename(suffix=".vcf")
        vcf_in = pysam.VariantFile(fn_in)

        vcf_out = pysam.VariantFile(fn_out, "w", header=vcf_in.header)
        for record in vcf_in:
            vcf_out.write(record)

        vcf_in.close()
        vcf_out.close()

        self.complete_check(fn_in, fn_out)

    def testConstructionWithLines(self):

        fn_in = os.path.join(CBCF_DATADIR, self.filename)
        fn_out = get_temp_filename(suffix=".vcf")
        vcf_in = pysam.VariantFile(fn_in)

        header = pysam.VariantHeader()
        for sample in vcf_in.header.samples:
            header.add_sample(sample)

        for hr in vcf_in.header.records:
            header.add_line(str(hr))

        vcf_out = pysam.VariantFile(fn_out, "w", header=header)

        for record in vcf_in:
            vcf_out.write(record)

        vcf_out.close()
        vcf_in.close()

        self.complete_check(fn_in, fn_out)


# class TestConstructionVCFWithoutContigs(TestConstructionVCFWithContigs):
#     """construct VariantFile from scratch."""
#     filename = "example_vcf40.vcf"


class TestConstructionVCFGZWithContigs(TestConstructionVCFWithContigs):
    """construct VariantFile from scratch."""

    filename = "example_vcf42_withcontigs.vcf.gz"
    compression = 'BGZF'
    description = 'VCF version 4.2 BGZF-compressed variant calling data'


class TestConstructionVCFGZWithoutContigs(TestConstructionVCFWithContigs):
    """construct VariantFile from scratch."""

    filename = "example_vcf42.vcf.gz"
    compression = 'BGZF'
    description = 'VCF version 4.2 BGZF-compressed variant calling data'


class TestSettingRecordValues(unittest.TestCase):

    filename = "example_vcf40.vcf"

    def testBase(self):
        with pysam.VariantFile(os.path.join(CBCF_DATADIR, self.filename)) as inf:
            self.assertEqual(inf.category, 'VARIANTS')
            self.assertEqual(inf.format, 'VCF')
            self.assertEqual(inf.version, (4, 0))
            self.assertEqual(inf.compression, 'NONE')
            self.assertEqual(
                inf.description, 'VCF version 4.0 variant calling text')
            self.assertTrue(inf.is_open)
            self.assertEqual(inf.is_read, True)
            self.assertEqual(inf.is_write, False)

    def testSetQual(self):
        with pysam.VariantFile(os.path.join(CBCF_DATADIR, self.filename)) as inf:
            record = next(inf)
            self.assertEqual(record.qual, 47)
            record.qual = record.qual
            self.assertEqual(record.qual, 47)
            record.qual = 10
            self.assertEqual(record.qual, 10)
            self.assertEqual(str(record).split("\t")[5], "10")

    def testGenotype(self):
        with pysam.VariantFile(os.path.join(CBCF_DATADIR, self.filename)) as inf:
            record = next(inf)
            sample = record.samples["NA00001"]
            print(sample["GT"])
            self.assertEqual(sample["GT"], (0, 0))
            sample["GT"] = sample["GT"]


class TestMultiThreading(unittest.TestCase):

    filename = os.path.join(CBCF_DATADIR, "example_vcf42.vcf.gz")

    def testSingleThreadEqualsMultithreadResult(self):
        with pysam.VariantFile(self.filename) as inf:
            header = inf.header
            single = [r for r in inf]
        with pysam.VariantFile(self.filename, threads=2) as inf:
            multi = [r for r in inf]
        for r1, r2 in zip(single, multi):
            assert str(r1) == str(r2)

        bcf_out = get_temp_filename(suffix=".bcf")
        with pysam.VariantFile(bcf_out, mode='wb',
                               header=header,
                               threads=2) as out:
            for r in single:
                out.write(r)
        with pysam.VariantFile(bcf_out) as inf:
            multi_out = [r for r in inf]
        for r1, r2 in zip(single, multi_out):
            assert str(r1) == str(r2)

    def testNoMultiThreadingWithIgnoreTruncation(self):
        with self.assertRaises(ValueError):
            pysam.VariantFile(self.filename,
                              threads=2,
                              ignore_truncation=True)


class TestSubsetting(unittest.TestCase):

    filename = "example_vcf42.vcf.gz"

    def testSubsetting(self):
        with pysam.VariantFile(os.path.join(CBCF_DATADIR,
                                            self.filename)) as inf:
            inf.subset_samples(["NA00001"])


class TestVCFVersions(unittest.TestCase):

    def setUp(self):
        self.files_to_test = (glob.glob(os.path.join(CBCF_DATADIR, "example_v*.vcf.gz")) +
                              glob.glob(os.path.join(CBCF_DATADIR, "example_v*.vcf")) +
                              glob.glob(os.path.join(CBCF_DATADIR, "example_v*.bcf")))
    
    def test_all_records_can_be_fetched(self):

        for fn in self.files_to_test:
            with pysam.VariantFile(fn) as inf:
                records = list(inf.fetch())


class TestUnicode(unittest.TestCase):
    filename = "example_vcf43_with_utf8.vcf.gz"

    def test_record_with_unicode(self):
        with pysam.VariantFile(os.path.join(CBCF_DATADIR,
                                            self.filename)) as inf:
            records = list(inf.fetch("20", 2345677, 2345678))
        self.assertEqual(len(records), 1)
        record = records.pop()
        self.assertEqual(
            record.info["CLNVI"],
            ('Institute_of_Human_Genetics', u'Friedrich-Alexander-Universität_Erlangen-Nürnberg'))
        self.assertEqual(record.samples[0]["AN"], "alpha")
        self.assertEqual(record.samples[1]["AN"], u"ä")
        self.assertEqual(record.samples[2]["AN"], u"ü")
                

if __name__ == "__main__":
    print("starting tests")
    unittest.main()
    print("completed tests")
