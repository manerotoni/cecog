import numpy
import logging
import matplotlib as mpl
from matplotlib.mlab import rec_append_fields, FormatFloat, rec2csv
from matplotlib import pyplot
import re
import os
import cPickle as pickle
from itertools import cycle
from cecog.colors import rgb2hex

from matplotlib.backends.backend_pdf import PdfPages
from vigra.impex import readImage
mpl.rcParams["figure.facecolor"] = 'w'
mpl.rcParams["pdf.compression"] = 0

import pylab

def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    return type('Enum', (), enums)

class EventPlotterPdf(object):
    def __init__(self, figsize):
        self.figure = pyplot.figure(figsize=figsize)
        self.figure.set_dpi(400)
        self.axes = self.figure.add_axes((0.1, 0.5, 0.8, 0.5))
        self._pdf_handle = None
        self.add_axes = {}
        self.normalize_gallery_image = True

    def clear(self):
        self.axes.cla()
        for a in self.add_axes.values():
            a.cla()

    def open(self, filename):
        self._pdf_handle = PdfPages(filename)

    def close(self):
        if self._pdf_handle is not None:
            self._pdf_handle.close()
            self._pdf_handle = None

    def save(self):
        self.figure.savefig(self._pdf_handle, format='pdf')


class GalleryDecorationPlotter(EventPlotterPdf):
    def set_positions(self):
        self.axes.set_position((0.1, 0.4, 0.8, 0.4))

        self.add_axes['gallery'].set_position((0.1, 0.1, 0.8, 0.4))
        self.add_axes['gallery'].set_frame_on(False)



    def add_gallery_deco(self, event_id, pos_name, path_in, time, class_labels,
                         class_colors, channel=('primary', 'secondary')):
        if 'gallery' not in self.add_axes:
            self.add_axes['gallery'] = self.figure.add_axes((0.1, 0.1, 0.8, 0.4))

        new_axes = self.add_axes['gallery']

        x_min = 0
        x_max = time[-1]+time[1]


        event_re = re.search(r"^T(?P<time>\d+)_O(?P<obj>\d+)_B(?P<branch>\d+)", event_id)
        t_ = int(event_re.groupdict()['time'])
        o_ = int(event_re.groupdict()['obj'])
        b_ = int(event_re.groupdict()['branch'])

        gallery_path = os.path.join(path_in, pos_name, 'gallery', 'primary')
        prim_gallery_file = os.path.join(gallery_path, 'P%s__T%05d__O%04d__B%02d.png' % (pos_name, t_, o_ , b_))

        gallery_path = os.path.join(path_in, pos_name, 'gallery', 'secondary')
        sec_gallery_file = os.path.join(gallery_path, 'P%s__T%05d__O%04d__B%02d.png' % (pos_name, t_, o_ , b_))

        if os.path.exists(prim_gallery_file):
            prim_img = readImage(prim_gallery_file)[:,:,0].view(numpy.ndarray).astype(numpy.uint8).swapaxes(1,0)
            if self.normalize_gallery_image:
                prim_img = ((prim_img - prim_img.min()) / float(prim_img.max() - prim_img.min()) * 255).astype(numpy.uint8)

            img = prim_img

            if os.path.exists(sec_gallery_file):
                sec_img = readImage(sec_gallery_file)[:,:,0].view(numpy.ndarray).astype(numpy.uint8).swapaxes(1,0)
                img = numpy.concatenate((prim_img, sec_img), axis=0)

            aspect = img.shape[0] / float(img.shape[1])
            offset = x_max*aspect



            new_axes.imshow(img, extent=(x_min, x_max, 0, offset), cmap=pyplot.get_cmap('gray'))

            new_axes.set_yticklabels([])

            for t in xrange(len(time)):
                if t >= len(time)-1:
                    w = time[1]
                else:
                    w = time[t+1]-time[t]
                new_axes.add_patch(pyplot.Rectangle((time[t], offset),
                                                      w,
                                                      offset*1.05,
                                                      fill=True,
                                                      color=class_colors[class_labels[t]]))
            new_axes.set_ylim(0, offset*1.05)
            new_axes.set_xlim(0, x_max)
            new_axes.set_xlabel("Time [min]")

            self.axes.set_xlabel("")
            self.axes.set_xticklabels([])
            self.axes.set_xticks([])


        self.set_positions()

class PostProcessingAnalysis(object):
    REJECTION = enum('OK', "BY_SPLIT", "BY_PROPHASE_ONSET")
    def __init__(self, path_in,
                       path_out,
                       plate_name,
                       mapping_file,
                       class_colors,
                       class_names):

        self.plate_name = plate_name
        self.path_in = path_in
        self.path_out = path_out
        self.mapping_file = mapping_file
        self.class_colors = class_colors
        self.class_names = class_names
        self.plate = None

    def _readScreen(self):
        if self.plate is None:
            self.plate = Plate(self.plate_name, self.path_in, self.mapping_file)

    def run(self):
        raise NotImplementedError

    def _run(self):
        raise NotImplementedError

    def _find_separation_event(self, h2b):
        # separation event found by isplit entry
        separation_frame = h2b['issplit'].nonzero()[0]
        if len(separation_frame) != 0:
            return self.__class__.REJECTION.OK, separation_frame[0]

        # try first early ana phase
        separation_frame = (h2b[self.plate.class_label_selector] == 5).nonzero()[0]
        if len(separation_frame) > 1:
            return self.__class__.REJECTION.OK, separation_frame[0]

        # try meta -> late ana transition
        transition = ''.join(map(str, h2b[self.plate.class_label_selector])).find('46') + 1
        if transition > 1:
            return self.__class__.REJECTION.OK, transition

        return self.__class__.REJECTION.BY_SPLIT, None

    def _find_prophase_onset(self, h2b, nebd_onset_frame=None):
        if nebd_onset_frame is None:
            nebd_onset_frame = len(h2b) / 2
        for x in reversed(range(nebd_onset_frame+2)):
            label = h2b[self.plate.class_label_selector][x]
            if label == 1:
                return IBBAnalysis.REJECTION.OK, x + 1
        return self.__class__.REJECTION.BY_PROPHASE_ONSET, None



class SecurinAnalysis(PostProcessingAnalysis):
    def __init__(self, path_in,
                       path_out,
                       plate_name,
                       mapping_file,
                       class_colors,
                       class_names,
                       **securin_settings):

        self._logger = logging.getLogger(self.__class__.__name__)
        PostProcessingAnalysis.__init__(self, path_in, path_out, plate_name, mapping_file, class_colors, class_names)
        self._plotter = {}
        self.single_plot = True
        self.single_plot_max_plots = 30
        self.single_plot_ylim_range = (0, 120)

    def run(self):
        try:
            self._readScreen()
            grouped_positions = self.plate.get_events()
            for group_name in grouped_positions:
                print group_name
                if self.single_plot:
                    self._plotter[group_name] = GalleryDecorationPlotter((15, 5))
                    self._plotter[group_name].open(os.path.join(self.path_out, 'securin__PL%s__%s__single_plots.pdf' % (self.plate_name, group_name)))
            self._run(grouped_positions)
        finally:
            for pl in self._plotter.values():
                pl.close()


    def _run(self, grouped_positions):
        print "Run Securin"
        result = {}
        for group_name, pos_list in grouped_positions.items():
            result[group_name] = {}
            result[group_name]['positions'] = []
            for pos in pos_list:
                cnt_single_plot = 0
                result[group_name]['positions'].append(pos)
                for event_idx, (event_id, event_dicts) in enumerate(sorted(pos.items())):
                    h2b = event_dicts['Primary']['primary']
                    securin_outside = event_dicts['Secondary']['expanded']

                    sec_signal = securin_outside['feature__n2_avg']

                    time = h2b['timestamp']
                    time = time - time[0]
                    rejection_code_split, separation_frame = self._find_separation_event(h2b)
                    rejection_code_prophase, prophase_onset_frame = self._find_prophase_onset(h2b)

                    securin_peak_decay = self._find_peak_decay(sec_signal)

                    if rejection_code_split != self.REJECTION.OK or \
                       rejection_code_prophase != self.REJECTION.OK:
                        print 'event rejected'


                    if self.single_plot and cnt_single_plot < self.single_plot_max_plots:
                            self._plot_single_event(group_name, sec_signal, h2b,
                                                    separation_frame,
                                                    prophase_onset_frame,
                                                    securin_peak_decay,
                                                    event_id, pos.position)
                            cnt_single_plot += 1


    def _plot_single_event(self, group_name, signal, h2b,
                           separation_frame,
                           prophase_onset,
                           securin_peak_decay,
                           event_id, pos_name):

        ya, yb = self.single_plot_ylim_range


        self._plotter[group_name].clear()
        axes = self._plotter[group_name].axes

        time = h2b['timestamp']
        time = time - time[0]
        time /= 60.0

        axes.plot(time, signal, 'k.-', label="Securin signal", axes=axes)
        if separation_frame is not None:
            axes.plot([time[separation_frame], time[separation_frame]], [ya, yb], 'r', label="Split",)
        if prophase_onset is not None:
            axes.plot([time[prophase_onset], time[prophase_onset]], [ya, yb/2.0], 'y', label="Pro Onset",)
        axes.plot([time[securin_peak_decay], time[securin_peak_decay]], [ya, yb/1.5], 'b', label="Peak decay",)

        axes.set_ylim(ya, yb)

        time_lapse_mean = numpy.array([a-b for a,b in zip(time[1:], time[0:])]).max()

        axes.set_xlim(0, time[-1]+time_lapse_mean)
        axes.set_title("%s - %s" % (group_name, event_id))
        axes.set_ylabel("IBB ratio")
        axes.set_xlabel("Time [min]")
#        pylab.text(time[separation_frame]+0.5, ratio.max(), "Sep", verticalalignment='top', color='r')
#        pylab.text(time[ibb_onset_frame]+0.5, ratio.max(), "Ibb", verticalalignment='top', color='g')
#        pylab.text(time[nebd_onset_frame]+0.5, ratio.max(), "Nebd", verticalalignment='top', color='b')
        axes.legend(loc="lower right", prop={'size': 6})
        axes.grid('on')

        class_labels = h2b[self.plate.class_label_selector]

        self._plotter[group_name].add_gallery_deco(event_id, pos_name, self.path_in, time, class_labels, self.class_colors)

        self._plotter[group_name].save()

    def _find_peak_decay(self, sec_signal):
        grad_sec_signal = numpy.diff(sec_signal)
        peak_decay_fram = numpy.argmin(grad_sec_signal[1:-1]) + 1
        return peak_decay_fram



class IBBAnalysis(PostProcessingAnalysis):
    REJECTION = enum('OK', "BY_SIGNAL", "BY_SPLIT", "BY_IBB_ONSET", "BY_NEBD_ONSET", "BY_PROPHASE_ONSET")
    IBB_ZERO_CORRECTION = 0.025
    COLOR_SORT_BY = ['position', 'oligoid', 'gene_symbol', 'group']

    PLOT_IDS =    ['nebd_to_sep_time', 'sep_to__ibb_time', 'prophase_to_nebd', 'nebd_to_last_prophase']
    PLOT_LABELS = {'nebd_to_sep_time': 'NEBD to Separation',
                   'sep_to__ibb_time': 'Separation to IBB Onset',
                   'prophase_to_nebd': 'Prophase Onset to NEBD',
                   'nebd_to_last_prophase': 'NEBD to Prometaphace Onset'
                   }

    def __init__(self, path_in,
                       path_out,
                       plate_name,
                       mapping_file,
                       class_colors,
                       class_names,
                       ibb_ratio_signal_threshold=1.0,
                       ibb_range_signal_threshold=0.5,
                       ibb_zero_correction=0.025,
                       ibb_onset_factor_threshold=1.2,
                       nebd_onset_factor_threshold=1.2,
                       single_plot=True,
                       single_plot_max_plots=1,
                       single_plot_ylim_range=(1,5),
                       group_by=0,
                       color_sort_by='gene_symbol',
                       timeing_ylim_range=(1,100)
                       ):
        self._logger = self._logger = logging.getLogger(self.__class__.__name__)
        PostProcessingAnalysis.__init__(self, path_in, path_out, plate_name, mapping_file, class_colors, class_names)

        self._plotter = {}

        self.ibb_ratio_signal_threshold = ibb_ratio_signal_threshold
        self.ibb_range_signal_threshold = ibb_range_signal_threshold
        self.ibb_onset_factor_threshold = ibb_onset_factor_threshold
        self.nebd_onset_factor_threshold = nebd_onset_factor_threshold

        self.single_plot = single_plot
        self.single_plot_max_plots = single_plot_max_plots
        self.single_plot_ylim_range = single_plot_ylim_range
        self.group_by = group_by
        self.color_sort_by = color_sort_by
        self.timeing_ylim_range = timeing_ylim_range

        self.class_label_selector = 'class__label'

    def run(self):
        try:
            self._readScreen()
            grouped_positions = self.plate.get_events()

            for group_name in grouped_positions:
                if self.single_plot:
                    self._plotter[group_name] = GalleryDecorationPlotter((15, 5))
                    self._plotter[group_name].open(os.path.join(self.path_out, 'ibb__PL%s__%s__single_plots.pdf' % (self.plate_name, group_name)))
            self._run(self.plate_name, grouped_positions)
        finally:
            for pl in self._plotter.values():
                pl.close()

    def _run(self, plate_id, grouped_positions):
        result = {}

        for group_name, pos_list in grouped_positions.items():
            result[group_name] = {}
            result[group_name]['positions'] = []

            result[group_name]['nebd_to_sep_time'] = []
            result[group_name]['sep_to__ibb_time'] = []
            result[group_name]['prophase_to_nebd'] = []
            result[group_name]['nebd_to_last_prophase'] = []
            result[group_name]['valid'] = [0,0,0,0,0,0]
            result[group_name]['timing'] = []

            for pos in pos_list:
                result[group_name]['positions'].append(pos)
                print pos.position, ":::",
                cnt_single_plot = 0
                for event_idx, (event_id, event_dicts) in enumerate(sorted(pos.items())):
                    print event_idx, event_id,
                    h2b = event_dicts['Primary']['primary']
                    ibb_inside = event_dicts['Secondary']['inside']
                    ibb_outside = event_dicts['Secondary']['outside']

                    ins = ibb_inside['feature__n2_avg'] + IBBAnalysis.IBB_ZERO_CORRECTION
                    out = ibb_outside['feature__n2_avg'] + IBBAnalysis.IBB_ZERO_CORRECTION
                    ibb_ratio = ins / out

                    rejection_code, ibb_result = self._analyze_ibb(h2b, ibb_ratio)
                    result[group_name]['valid'][rejection_code] += 1

                    time = h2b['timestamp']
                    time = time - time[0]

                    if rejection_code == IBBAnalysis.REJECTION.OK:
                        separation_frame, ibb_onset_frame, nebd_onset_frame, prophase_onset, prophase_last_frame = ibb_result

                        result[group_name]['nebd_to_sep_time'].append(time[separation_frame] - time[nebd_onset_frame])
                        result[group_name]['sep_to__ibb_time'].append(time[ibb_onset_frame] - time[separation_frame])
                        result[group_name]['prophase_to_nebd'].append(time[nebd_onset_frame] - time[prophase_onset])
                        result[group_name]['nebd_to_last_prophase'].append(time[prophase_last_frame] - time[nebd_onset_frame])

                        result[group_name]['timing'].append(self._find_class_timing(h2b, time[1]))

                        if self.single_plot and cnt_single_plot < self.single_plot_max_plots:
                            self._plot_single_event(group_name, ibb_ratio, h2b,
                                                    separation_frame,
                                                    ibb_onset_frame,
                                                    nebd_onset_frame,
                                                    prophase_onset,
                                                    prophase_last_frame,
                                                    event_id, pos.position)
                            cnt_single_plot += 1
                print ""
            if group_name in self._plotter:
                self._plotter[group_name].close()
        self.export_class_timing(result)
        self.export_timing(result, "nebd_to_sep_time")
        self.export_timing(result, "sep_to__ibb_time")
        self.export_timing(result, "prophase_to_nebd")
        self.export_timing(result, "nebd_to_last_prophase")

        self._plot_valid_bars(result)
        self._plot(result, "nebd_to_sep_time")
        self._plot(result, "sep_to__ibb_time")
        self._plot(result, "prophase_to_nebd")
        self._plot(result, "nebd_to_last_prophase")
        self._plot_timing(result)

    def export_class_timing(self, result):
        for class_index, class_name in sorted(self.class_names.items()):
            filename = os.path.join(self.path_out, '_class_timing_%02d_%s.txt' % (class_index, class_name)  )
            data = []
            names = []

            for group_name in sorted(result):
                group_data = []
                names.append(group_name)
                tmp_data = result[group_name]['timing']
                for class_counts in tmp_data:
                    if class_index in class_counts:
                        tmp = class_counts[class_index]
                        if isinstance(tmp, list):
                            group_data.extend(class_counts[class_index])
                        else:
                            group_data.append(class_counts[class_index])

                data.append(group_data)
            self._export_data_list(filename, data, names)

    def _export_data_list(self, filename, data, names):

        class FormatFloatNaN(FormatFloat):
            def tostr(self, val):
                result = FormatFloat.tostr(self, val)
                if result == 'nan':
                    return ''
                return result

        dtype = [(n, 'float') for n in names]
        fnan = FormatFloatNaN()
        formatd = dict([(n, fnan) for n in names])

        data_t = numpy.array(map(None, *data), dtype=dtype)
        mpl.mlab.rec2csv(data_t, filename, formatd=formatd, delimiter='\t')

    def export_timing(self, result, id_):
        data = []
        names = []

        for group_name in sorted(result):

            data.append(numpy.array(result[group_name][id_])/60.0)
            if isinstance(group_name, int):
                names.append("%04d" % group_name)
            else:
                names.append("%s" % group_name)

        filename = os.path.join(self.path_out, '_timing_ibb_events_%s.txt' % id_)
        self._export_data_list(filename, data, names)

    def _plot_timing(self, result):
        f_handle = PdfPages(os.path.join(self.path_out, '_class_timing.pdf' ))

        for class_index, class_name in sorted(self.class_names.items()):
            data = []
            names = []

            for group_name in sorted(result):
                group_data = []
                names.append(group_name)
                tmp_data = result[group_name]['timing']
                for class_counts in tmp_data:
                    if class_index in class_counts:
                        tmp = class_counts[class_index]
                        if isinstance(tmp, list):
                            group_data.extend(class_counts[class_index])
                        else:
                            group_data.append(class_counts[class_index])

                data.append(group_data)

            self._plot_single_class_timing(data, names, class_name, self.class_colors[class_index], f_handle)

        f_handle.close()

    def _plot_single_class_timing(self, data, names, class_name, class_color, f_handle):
        fig = pyplot.figure(figsize=(len(data)+5, 10))
        ax = fig.add_subplot(111)
        ax.bar(range(len(data)), map(numpy.mean, numpy.array(data)),
               width=0.6,
               yerr=map(numpy.std, numpy.array(data)),
               color=class_color,
               ecolor='k',
               align='center',
               )
        ax.set_xticks(range(len(data)))
        xtick_labels = ax.set_xticklabels(names)
        pyplot.setp(xtick_labels, rotation=45,  horizontalalignment='right', fontsize=12)
        ax.set_title(class_name)
        ax.set_ylabel('Time [min]')
        ax.set_ylim(*self.timeing_ylim_range)
        fig.savefig(f_handle, format='pdf')

    def _analyze_ibb(self, h2b, ibb_ratio):
        rejection_code, separation_frame = self._find_separation_event(h2b)
        if rejection_code != IBBAnalysis.REJECTION.OK:
            return rejection_code, None


        rejection_code = self._check_signal(ibb_ratio)
        if rejection_code != IBBAnalysis.REJECTION.OK:
            return rejection_code, None

        rejection_code, ibb_onset_frame = self._find_ibb_onset_event(ibb_ratio, separation_frame)
        if rejection_code != IBBAnalysis.REJECTION.OK:
            return rejection_code, None

        rejection_code, nebd_onset_frame = self._find_nebd_onset_event(ibb_ratio, separation_frame)
        if rejection_code != IBBAnalysis.REJECTION.OK:
            return rejection_code, None

        rejection_code, prophase_onset = self._find_prophase_onset(h2b, nebd_onset_frame)
        if rejection_code != IBBAnalysis.REJECTION.OK:
            return rejection_code, None

        rejection_code, prophase_last_frame = self._find_prophase_last_frame(h2b, nebd_onset_frame, separation_frame)
        if rejection_code != IBBAnalysis.REJECTION.OK:
            return rejection_code, None

        return IBBAnalysis.REJECTION.OK, (separation_frame, ibb_onset_frame, nebd_onset_frame, prophase_onset, prophase_last_frame)


    def _find_prophase_last_frame(self, h2b, nebd_onset_frame, separation_frame):
        for x in range(nebd_onset_frame, separation_frame):
            label = h2b[self.plate.class_label_selector][x]
            label_next = h2b[self.plate.class_label_selector][x+1]
            if label == 2 and label_next != 2:
                return IBBAnalysis.REJECTION.OK, x+1

        for x in range(nebd_onset_frame, 1, -1):
            label = h2b[self.plate.class_label_selector][x]
            label_next = h2b[self.plate.class_label_selector][x-1]
            if label_next == 2 and label != 2:
                return IBBAnalysis.REJECTION.OK, x

        return IBBAnalysis.REJECTION.BY_NEBD_ONSET, None

    def _get_relative_time(self, h2b, frame_idx):
        return h2b['timestamp'][frame_idx] - h2b['timestamp'][0]


    def _check_signal(self, ibb_ratio):
        if ibb_ratio.mean() < self.ibb_ratio_signal_threshold or \
           (ibb_ratio.max() - ibb_ratio.min()) < self.ibb_range_signal_threshold:
            return IBBAnalysis.REJECTION.BY_SIGNAL

        return IBBAnalysis.REJECTION.OK

    def _find_ibb_onset_event(self, ibb_ratio, separation_frame):
        ibb_onset_frame = separation_frame - 1
        while True:
            if ibb_ratio[ibb_onset_frame] >= ibb_ratio[separation_frame] * self.ibb_onset_factor_threshold:
                ibb_onset_frame -= 1
                break
            elif ibb_onset_frame >= len(ibb_ratio)-2:
                ibb_onset_frame = None
                break
            ibb_onset_frame += 1

        if ibb_onset_frame is None:
            return self.REJECTION.BY_IBB_ONSET, None

        return IBBAnalysis.REJECTION.OK, ibb_onset_frame

    def _find_class_timing(self, h2b, time_lapse):
        class_labels = h2b[self.plate.class_label_selector]

        class_timing = {}
        for c in class_labels:
            if c not in class_timing:
                class_timing[c] = 0
            class_timing[c] += 1

        for c in class_timing:
            class_timing[c] = class_timing[c] * time_lapse / 60.0

        return class_timing

    def _find_nebd_onset_event(self, ibb_ratio, separation_frame):
        nebd_onset_frame = ibb_ratio.argmin() + 1

        if nebd_onset_frame > separation_frame:
            nebd_onset_frame = separation_frame

        while True:
            nebd_onset_frame -= 1
            if ibb_ratio[nebd_onset_frame] / ibb_ratio[nebd_onset_frame+1] >= self.nebd_onset_factor_threshold:
                break
            elif nebd_onset_frame <= 0:
                nebd_onset_frame = None
                break

        if nebd_onset_frame is None:
            return IBBAnalysis.REJECTION.BY_NEBD_ONSET, None

        nebd_onset_frame += 1
        return IBBAnalysis.REJECTION.OK, nebd_onset_frame

    def _plot_single_event(self, group_name, ratio, h2b,
                           separation_frame,
                           ibb_onset_frame,
                           nebd_onset_frame,
                           prophase_onset,
                           prophase_last_frame,
                           event_id, pos_name):

        ya, yb = self.single_plot_ylim_range


        self._plotter[group_name].clear()
        figure = self._plotter[group_name].figure
        axes = self._plotter[group_name].axes

        time = h2b['timestamp']
        time = time - time[0]
        time /= 60.0

        axes.plot(time, ratio, 'k.-', label="Ibb ratio", axes=axes)
        axes.plot([time[separation_frame], time[separation_frame]], [ya, yb], 'r', label="Split",)
        axes.plot([time[ibb_onset_frame], time[ibb_onset_frame]], [ya, yb], 'g', label="IBB Onset",)
        axes.plot([time[nebd_onset_frame], time[nebd_onset_frame]], [ya, yb], 'b', label="NEBD",)
        axes.plot([time[prophase_onset], time[prophase_onset]], [ya, yb/2.0], 'y', label="Pro Onset",)
        axes.plot([time[prophase_last_frame], time[prophase_last_frame]], [ya, yb/2.0], 'c', label="Prometa Onset",)

        axes.set_ylim(ya, yb)

        time_lapse_mean = numpy.array([a-b for a,b in zip(time[1:], time[0:])]).max()

        axes.set_xlim(0, time[-1]+time_lapse_mean)
        axes.set_title("%s - %s" % (group_name, event_id))
        axes.set_ylabel("IBB ratio")
        axes.set_xlabel("Time [min]")
        axes.legend(loc="lower right", prop={'size': 6})
        axes.grid('on')

        class_labels = h2b[self.plate.class_label_selector]

        self._plotter[group_name].add_gallery_deco(event_id, pos_name, self.path_in, time, class_labels, self.class_colors)

        self._plotter[group_name].save()

    def _plot(self, result, id_):
        data = []
        names = []
        colors = []
        base_colors = cycle([tuple(x) for x in (pyplot.cm.Set3(range(0,256,24))*255).astype('uint8')[:,:3]])
        def mycmp(x, y):
            return cmp(result[x]['positions'][0].__getattribute__(self.color_sort_by).lower(),
                       result[y]['positions'][0].__getattribute__(self.color_sort_by).lower())

        last_id = 'hamster'
        neg_ctrl = []
        for group_name in sorted(result, cmp=mycmp):
            new_id = result[group_name]['positions'][0].__getattribute__(self.color_sort_by)

            data.append(numpy.array(result[group_name][id_])/60.0)
            if result[group_name]['positions'][0].group == 'neg ctrl':
                neg_ctrl.append(numpy.array(result[group_name][id_])/60.0)

            if isinstance(group_name, int):
                names.append("%s (%43d)" % (new_id, group_name))
            else:
                names.append("%s (%s)" % (new_id, group_name))

            if last_id != new_id:
                color = base_colors.next()
                last_id = result[group_name]['positions'][0].__getattribute__(self.color_sort_by)
            colors.append(color)

        self._boxplot(data, names, colors, id_, neg_ctrl)
        self._barplot(data, names, colors, id_, neg_ctrl)

    def _plot_valid_bars(self, result):
        data = []
        names = []
        bar_labels = ('valid', 'signal', 'split', 'ibb_onset', 'nebd_onset', 'prophase_onset')
        bar_colors = map(lambda x:rgb2hex(x, mpl=False), [[int(x*255) for x in pyplot.cm.Greens(2)[0:3]],] +
                                                  [tuple(x) for x in (pyplot.cm.RdBu(range(0,256,62))*255)[:,:3].astype('uint8')[:,:3]]
                          )


        def mycmp(x, y):
            return cmp(result[x]['positions'][0].__getattribute__(self.color_sort_by).lower(),
                       result[y]['positions'][0].__getattribute__(self.color_sort_by).lower())

        for group_name in sorted(result, cmp=mycmp):
            data.append(result[group_name]['valid'])
            names.append(group_name)

        self._plot_multi_bars(data, bar_labels, bar_colors, names, show_number=False)

    def _plot_multi_bars(self, data, bar_labels, bar_colors, names, show_number=True):
        """plot_valid_bars([(10, 4, 1), (11,3,2), (7,6, 4), (14,3,1)], ('valied', 'bad', 'distgusting'), ('r', 'g', 'b'), ('G1', 'G2', 'G3', 'G4','G5'))
        """
        def autolabel(rects):
        # attach some text labels
            for rect in rects:
                height = rect.get_height()
                rect.get_axes().text(rect.get_x()+rect.get_width()/2., 1.05*height, '%d'%int(height),
                        ha='center', va='bottom')
        fig = pyplot.figure(figsize=(len(data)+5,10))
        ax = fig.add_subplot(111)

        data_t = zip(*data)
        N = len(data)
        ind = numpy.arange(N).astype(numpy.float32)
        width = 0.8 / len(data[0])

        for i, d in enumerate(data_t):
            rect = ax.bar(ind, d, width, color=bar_colors[i], label=bar_labels[i])
            if show_number:
                autolabel(rect)
            ind += width

        ax.set_ylabel('Count')
        ax.set_xticks(numpy.arange(N).astype(numpy.float32)+0.4)
        xtick_labels = ax.set_xticklabels(names)
        pyplot.setp(xtick_labels, rotation=45, horizontalalignment='right', fontsize=12)
        ax.legend(loc=1)

        fig.savefig(os.path.join(self.path_out, '_valid_events.pdf'), format='pdf')

    def _barplot(self, data_list, names, colors, id_, neg_ctrl):
        fig = pyplot.figure(figsize=(len(data_list)/3+5, 20))
        ax1 = fig.add_subplot(111)
        ax1.set_title('IBB Analysis %s' % self.PLOT_LABELS[id_])
        ax1.bar(range(len(data_list)), map(numpy.mean, numpy.array(data_list)),
                yerr=map(numpy.std, numpy.array(data_list)),
                color=map(lambda x:rgb2hex(x, mpl=False), colors),
                ecolor='k',
                align='center',
                )
        #ax1.set_xticks([x+0.8 for x in range(len(data_list))])

        if len(neg_ctrl) > 0:
            neg_line = numpy.concatenate(neg_ctrl).mean()
            ax1.plot([0, len(data_list)],[neg_line, neg_line], 'k--', label="Neg. Ctrl.")
        #xtickNames = pyplot.setp(ax1, xticklabels=names)
        #pyplot.setp(xtickNames, rotation=45, horizontalalignment='right', fontsize=10)
        ax1.set_xticks(range(len(data_list)))
        xticks = ax1.set_xticklabels(names)
        pyplot.setp(xticks, rotation=45,  horizontalalignment='right')

        pyplot.ylim(*self.timeing_ylim_range)

        data_max = numpy.nanmax(numpy.array(map(numpy.mean, numpy.array(data_list))))
        if data_max < 0.5 * self.timeing_ylim_range[1]:
            pyplot.ylim(self.timeing_ylim_range[0], self.timeing_ylim_range[1]/2.0)
        if data_max < 0.25 * self.timeing_ylim_range[1]:
            pyplot.ylim(self.timeing_ylim_range[0], self.timeing_ylim_range[1]/4.0)
        if data_max < 0.125 * self.timeing_ylim_range[1]:
            pyplot.ylim(self.timeing_ylim_range[0], self.timeing_ylim_range[1]/8.0)

        fig.savefig(os.path.join(self.path_out, '_timing_ibb_events_%s_bar.pdf' % id_), format='pdf')

    def _boxplot(self, data_list, names, colors, id_, neg_ctrl):
        fig = pyplot.figure(figsize=(len(data_list)/3+5, 20))
        ax1 = fig.add_subplot(111)
        ax1.set_title('IBB Analysis %s' % self.PLOT_LABELS[id_])
        bp = pyplot.boxplot(data_list, patch_artist=True)
        pyplot.setp(bp['boxes'], color='black')
        pyplot.setp(bp['whiskers'], color='black')
        pyplot.setp(bp['fliers'], markerfacecolor='w', marker='o', markeredgecolor='k')
        i = 0
        for c, d in zip(colors, data_list):
            if len(d) > 0:
                b = bp['boxes'][i]
                pyplot.setp(b, facecolor=rgb2hex(c, mpl=False))
                i += 1

        #ax1.set_xticks([x+0.8 for x in range(len(data_list))])
        if len(neg_ctrl) > 0:
            neg_line = numpy.concatenate(neg_ctrl).mean()
            ax1.plot([0, len(data_list)],[neg_line, neg_line], 'k--', label="Neg. Ctrl.")
        xtickNames = pyplot.setp(ax1, xticklabels=names)
        pyplot.setp(xtickNames, rotation=45, horizontalalignment='right', fontsize=10)

        data_max = numpy.nanmax(numpy.array(map(numpy.mean, numpy.array(data_list))))
        if data_max < 0.5 * self.timeing_ylim_range[1]:
            pyplot.ylim(self.timeing_ylim_range[0], self.timeing_ylim_range[1]/2.0)
        if data_max < 0.25 * self.timeing_ylim_range[1]:
            pyplot.ylim(self.timeing_ylim_range[0], self.timeing_ylim_range[1]/4.0)
        if data_max < 0.125 * self.timeing_ylim_range[1]:
            pyplot.ylim(self.timeing_ylim_range[0], self.timeing_ylim_range[1]/8.0)

        fig.savefig(os.path.join(self.path_out, '_timing_ibb_events_%s_box.pdf' % id_), format='pdf')

class Position(dict):

    def __init__(self, plate,
                 position,
                 well,
                 site,
                 row,
                 column,
                 gene_symbol,
                 oligoid,
                 group):

        dict.__init__(self)
        self.plate = plate
        if isinstance(position, int):
            position = '%03d' % position
        self.position = str(position)
        self.well = str(well)
        self.site = site
        self.row = row
        self.column = column
        self.gene_symbol = str(gene_symbol)
        self.oligoid = str(oligoid)
        self.group = str(group)


    def __str__(self):
        return "p %s, o %s, g %s, g %s" % ( self.position, self.oligoid, self.gene_symbol, self.group)

    def __repr__(self):
        return "p %s, o %s, g %s, g %s" % ( self.position, self.oligoid, self.gene_symbol, self.group)


class Plate(object):

    GROUP_BY = enum('POS', "OLIGO", "GENE", "GROUP")

    POSITION_REGEXP = re.compile(r"^[A-Z]\d{1,5}_\d{1,5}$|^\d{1,6}$")
    EVENT_REGEXP = re.compile(r"features__P(?P<pos>\d+|[A-Z]\d+_\d+)__T(?P<time>\d+)"
                               "__O(?P<obj>\d+)__B(?P<branch>\d+)__C(?P<channel>.+?)__R(?P<region>.*)\.txt")

    def __init__(self, plate_id, path_in, mapping_file, group_by=0):
        self._logger =  self._logger = logging.getLogger(self.__class__.__name__)
        self.class_label_selector = 'class__label'
        self.plate_id = plate_id
        self.path_in = path_in
        self.mapping_file = mapping_file
        self._positions = {}
        self.group_by = group_by
        self.readEvents()

    def __str__(self):
        res = ""
        for pos in self._positions:
            res += "%s with %d events\n" % (pos, len(self._positions[pos]))
        return res

    def __repr_(self):
        res = ""
        for pos in self._positions:
            res += "%s with %d events\n" % (pos, len(self._positions[pos]))
        return res

    def _get_positions_dirs(self):
        pos_list = []
        for pos_candidate in sorted(os.listdir(self.path_in)):
            if self.POSITION_REGEXP.search(pos_candidate) is not None:
                pos_list.append(pos_candidate)

        if len(pos_list) == 0:
            raise RuntimeError("No positions folder found for path %s" % self.path_in)

        return pos_list

    def readEvents(self):
        self.mapping = self._readMappingFile()
        self.pos_list = self._get_positions_dirs()

        fmt = "%%0%dd" %(len(self.pos_list[0]))

        for pos_idx, pos_name in enumerate(self.mapping['position']):
            if isinstance(pos_name, int):
                pos_name = fmt %pos_name
            print pos_name, pos_name in self.pos_list
            if pos_name not in self.pos_list:
#                raise RuntimeError("Position from Mapping file %s not found in in path %s" % (pos_name, self.path_in))
                print "Position from Mapping file %s not found in in path %s" % (pos_name, self.path_in)
                self._logger.warning("Position from Mapping file %s not found in in path %s" % (pos_name, self.path_in))
                continue

            event_path = os.path.join(self.path_in, pos_name, 'statistics' , 'events')
            if not os.path.exists(event_path):
                raise RuntimeError("For position %s no event path found %s" % (pos_name, event_path))

            event_file_list = sorted(os.listdir(event_path))
            if len(event_file_list) == 0:
                self._logger.warning("No events found for position %s" % pos_name)
                continue

            self._logger.info("Reading Events for position '%s' (%d files)" % (pos_name, len(event_file_list)))

            hmm_correction_available = False
            if '_hmm' in event_file_list:
                hmm_correction_available = True
                event_file_list.remove('_hmm')

            for event_file in event_file_list:
                res = self.EVENT_REGEXP.search(event_file)
                if res is None:
                    self._logger.warning("Could not parse event file name '%s' for position %s" % (event_file, pos_name))
                    continue

                res = res.groupdict()
                if pos_name != res['pos']:
                    self._logger.error("Event file %s has different pos identifier than %s" % (event_file, pos_name))
                    raise RuntimeError("Event file %s has different pos identifier than %s" % (event_file, pos_name))

                channel = res["channel"]
                region = res["region"]
                branch = int(res["branch"])
                time = int(res["time"])
                obj = int(res["obj"])

                if branch != 1:
                    continue

                if pos_name not in self._positions.keys():
                    if 'oligoid' in self.mapping.dtype.fields.keys():
                        self.oligo_header_name = 'oligoid'
                    elif 'sirna_id' in self.mapping.dtype.fields.keys():
                        self.oligo_header_name = 'sirna_id'
                    else:
                        raise RuntimeError('Mapping file has no header: oligoid or siRNA_id missing')

                    self._positions[pos_name] = Position(plate=self.plate_id,
                                                        position=self.mapping[pos_idx]['position'],
                                                        well=self.mapping[pos_idx]['well'],
                                                        site=self.mapping[pos_idx]['site'],
                                                        row=self.mapping[pos_idx]['row'],
                                                        column=self.mapping[pos_idx]['column'],
                                                        gene_symbol=self.mapping[pos_idx]['gene_symbol'],
                                                        oligoid=self.mapping[pos_idx][self.oligo_header_name],
                                                        group=self.mapping[pos_idx]['group'],
                                                        )

                event_id = 'T%03d_O%04d_B%d' % (time, obj, branch)
                if event_id not in self._positions[pos_name]:
                    self._positions[pos_name][event_id] = {}

                if channel not in self._positions[pos_name][event_id]:
                    self._positions[pos_name][event_id][channel] = {}

                filename = os.path.join(event_path, event_file)
                self._positions[pos_name][event_id][channel][region] = numpy.recfromcsv(filename, delimiter='\t')

                if hmm_correction_available and region == 'primary':

                    filename = os.path.join(event_path, '_hmm', event_file)
                    if not os.path.exists(filename):
                        raise RuntimeError('HMM correction folder is there but event file not found %s' % filename)
                    class__label__hmm = numpy.recfromcsv(filename, delimiter='\t')['class__b__label']
                    self._positions[pos_name][event_id][channel][region] = \
                        rec_append_fields(self._positions[pos_name][event_id][channel][region],
                                          'class__label__hmm',
                                          class__label__hmm,
                                          numpy.uint8)

                    self.class_label_selector = 'class__label__hmm'
        self.save(True)

    def _readMappingFile(self):
        if os.path.exists(self.mapping_file):
            mapping = numpy.recfromcsv(self.mapping_file, delimiter='\t', comments='###')
        else:
            raise RuntimeError("Mapping file does not exist %s" % self.mapping_file)

        if len(mapping.shape) == 0:
            # stupid numpy bug, when the tsv file contains one single entry
            mapping.shape = (1,)

        if mapping.shape[0] == 0:
            raise RuntimeError("Mapping file is empty %s" % self.mapping_file)

        self._logger.info('Found mapping file: %s' % self.mapping_file)

        return mapping

    def get_events(self):
        res = {}

        for pos in self._positions.values():
            if self.group_by == self.GROUP_BY.POS:
                group_key = pos.position
            elif self.group_by == self.GROUP_BY.OLIGO:
                group_key = pos.oligoid
            elif self.group_by == self.GROUP_BY.GENE:
                group_key = pos.gene_symbol
            elif self.group_by == self.GROUP_BY.GROUP:
                group_key = pos.group
            else:
                raise AttributeError("group_by argument not understood %r" % self.group_by)

            if pos.position not in res:
                res[group_key] = []
            res[group_key].append(pos)
        return res

    def save(self, overwrite=False):
        if os.path.exists(os.path.join(self.path_in, self.plate_id + ".pkl")) and not overwrite:
            return
        f = open(os.path.join(self.path_in, self.plate_id + ".pkl"), 'w')
        self._logger.info('Saving plate %s to disk...' % self.plate_id)
        pickle.dump(self, f)
        f.close()

    @staticmethod
    def load(path_in, plate_id):
        try:
            print 'Loading of %s...' % os.path.join(path_in, plate_id + ".pkl"),
            filename = os.path.join(path_in, plate_id + ".pkl")
            if os.path.exists(filename):
                f = open(filename, 'r')
                plate = pickle.load(f)
                f.close()
                print 'done'
            else:
                print 'pkl file not found'
                plate = None
        except Exception as e:
            print 'failed'
            print str(e)
            plate = None
        return plate

    def __getstate__(self):
        d = dict(self.__dict__)
        del d['_logger']
        return d

    def __setstate__(self, d):
        self.__dict__.update(d)
        self._logger = logging.getLogger(self.__class__.__name__)


def test_plate():
    Plate("plate_name", r"C:\Users\sommerc\data\cecog\Analysis\H2b_aTub_MD20x_exp911_2_channels_zip\analyzed",
                            r"C:\Users\sommerc\data\cecog\Mappings\plate_name.txt")


def test_plate_2():
    a = Plate("plate_name", r"Y:\amalie\Analysis\001872_2_longer\analyzed",
                            r"Y:\amalie\Mappings\001872\001872.txt")

    a.save()

def test_ibb():
    class_colors = {1: '#00ff00',
                    2: '#fff643',
                    3: '#ff8000',
                    4: '#d28dce',
                    5: '#8931ea',
                    6: '#5871f1',
                    7: '#94b22d',
                    8: '#FF0000',
                    9: '#ff00ff',}

    ibb = IBBAnalysis("Y:/amalie/Analysis/001872_2_longer/analyzed",
                      "Y:/amalie/Analysis/001872_2_longer",
                      'plate_name',
                      r"C:\Users\sommerc\data\cecog\Mappings\plate_name.txt",
                      class_colors)

    ibb.run()

if __name__ == "__main__":
    test_ibb()
