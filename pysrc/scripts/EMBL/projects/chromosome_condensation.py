from optparse import OptionParser

import scripts.EMBL.projects.post_processing
reload(scripts.EMBL.projects.post_processing)

from scripts.EMBL.projects.post_processing import *

# export PYTHONPATH=/Users/twalter/workspace/cecog/pysrc

class ChromosomeCondensationAnalysis(PostProcessingWorkflow, FeatureProjectionAnalysis):
    def __init__(self, settings_filename=None, settings=None):
        if settings is None and settings_filename is None:
            raise ValueError("Either a settings object or a settings filename has to be given.")
        if not settings is None:
            self.settings = settings
        elif not settings_filename is None:
            self.settings = Settings(os.path.abspath(settings_filename), dctGlobals=globals())
        PostProcessingWorkflow.__init__(self, settings=self.settings)
        FeatureProjectionAnalysis.__init__(self, settings=self.settings)

        self._classifiers = {'lda': None, 'svm': None, 'logres': None}
        self._classifiers_fs = {'lda': None, 'svm': None, 'logres': None}


    def _apply_qc(self, track_data):
        track_data['qc'] = True

        # primary classification
        event_index = track_data['isEvent'].index(True)
        classification_results = track_data['primary']['primary']['class__name']

        # first rule: when interphase is reached without going through late mitotic phases
        if classification_results[event_index:event_index+5].count('inter') > 3:
            track_data['qc'] = False
            return

        return

    def _process(self, impdata):

        # reduce data set by QC
        self.applyQC(impdata, remove_qc_false=True, verbose=True)

        # calc the LDA projections
        self.calcProjections(impdata, channels=['primary'], regions=['primary'])

        # normalize features
        features = self.settings.features_normalization
        self.normalizeFeatures(impdata, features, channels=['primary'], regions=['primary'])

        return


if __name__ ==  "__main__":

    description =\
'''
%prog - generation of single cell html pages.
Prerequesites are gallery images (generated by scripts.cutter.cut_tracks_from_resultfile.py ) ,
a settings file for the whole workflow (like scripts/EMBL/settings_files/lamin/settings_lamin_analysis.py)
and the generated single cell plots. The scripts just links existing information together.
'''

    parser = OptionParser(usage="usage: %prog [options]",
                          description=description)

    parser.add_option("-s", "--settings_file", dest="settings_file",
                      help="Filename of the settings file for the postprocessing")
    parser.add_option("--plot_generation", action="store_true", dest="plot_generation",
                      help="Flag for plot generation (default is False)")
    parser.add_option("--panel_generation", action="store_true", dest="panel_generation",
                      help="Flag for panel generation (representation of "
                      "classification results to be used with gallery images.")
    parser.add_option("--plate", dest="plate",
                      help="Plate Identifier (default None; plates are then taken"
                      "from the settings files.")
    parser.add_option("--export", action="store_true", dest="export",
                      help="Flag for export: if set, all imported features are exported"
                      "to pickle files.")

    (options, args) = parser.parse_args()

    if (options.settings_file is None):
        parser.error("incorrect number of arguments!")

    plot_generation = options.plot_generation
    if plot_generation is None:
        plot_generation = False

    panel_generation = options.panel_generation
    if panel_generation is None:
        panel_generation = False

    cca = ChromosomeCondensationAnalysis(options.settings_file)
    if not options.plate is None:
        cca.settings.plates = [options.plate]

    # plot generation
    if plot_generation:
        cca.batchPlotGeneration()

    # plot generation
    export = options.export
    if export:
        cca.batchExport()

    # make HTML pages
    if panel_generation:
        cca.batchPanelGeneration()

    # generation of html-pages
    cca.batchHTMLPageGeneration()


