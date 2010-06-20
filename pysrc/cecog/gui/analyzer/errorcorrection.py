"""
                           The CellCognition Project
                     Copyright (c) 2006 - 2010 Michael Held
                      Gerlich Lab, ETH Zurich, Switzerland
                              www.cellcognition.org

              CellCognition is distributed under the LGPL License.
                        See trunk/LICENSE.txt for details.
                 See trunk/AUTHORS.txt for author contributions.
"""

__author__ = 'Michael Held'
__date__ = '$Date$'
__revision__ = '$Rev$'
__source__ = '$URL$'

__all__ = ['ErrorCorrectionFrame']

#-------------------------------------------------------------------------------
# standard library imports:
#

#-------------------------------------------------------------------------------
# extension module imports:
#

#-------------------------------------------------------------------------------
# cecog imports:
#
from cecog.traits.analyzer.errorcorrection import SECTION_NAME_ERRORCORRECTION
from cecog.gui.analyzer import (_BaseFrame,
                                _ProcessorMixin,
                                HmmThread
                                )

#-------------------------------------------------------------------------------
# constants:
#


#-------------------------------------------------------------------------------
# functions:
#


#-------------------------------------------------------------------------------
# classes:
#
class ErrorCorrectionFrame(_BaseFrame, _ProcessorMixin):

    SECTION_NAME = SECTION_NAME_ERRORCORRECTION
    DISPLAY_NAME = 'Error Correction'

    def __init__(self, settings, parent):
        _BaseFrame.__init__(self, settings, parent)
        _ProcessorMixin.__init__(self)

        self.register_control_button('hmm',
                                     HmmThread,
                                     ('Correct errors', 'Stop correction'))

        self.add_input('filename_to_r')
        self.add_line()
        self.add_group('constrain_graph',
                       [('primary_graph',),
                        ('secondary_graph',),
                        ])
        self.add_group('position_labels',
                       [('mappingfile',),
                        ])
        self.add_group(None,
                       [('groupby_position',),
                        ('groupby_oligoid',),
                        ('groupby_genesymbol',),
                        ], layout='flow', link='groupby', label='Group by')
        self.add_line()
        self.add_group(None,
                       [('timelapse',),
                        ('max_time',),
                        ], layout='flow', link='plot_parameter',
                        label='Plot parameter')
        self.add_expanding_spacer()
        self._init_control(has_images=False)

    def _get_modified_settings(self, name):
        settings = _ProcessorMixin._get_modified_settings(self, name)
        settings.set_section('Processing')
        if settings.get2('primary_classification'):
            settings.set2('primary_errorcorrection', True)
        if not settings.get2('secondary_processchannel'):
            settings.set2('secondary_classification', False)
            settings.set2('secondary_errorcorrection', False)
        elif settings.get2('secondary_classification'):
            settings.set2('secondary_errorcorrection', True)
        return settings