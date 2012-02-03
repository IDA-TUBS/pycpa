"""
| Copyright (C) 2007-2012 Jonas Diemer, Philip Axer
| TU Braunschweig, Germany
| All rights reserved

:Authors:
         - Jonas Diemer
         - Philip Axer

Description
-----------

General purpose plotting functions:
* event model plotting
* gantt plotting (requires the simulation engine)
"""


try:
    from matplotlib import ticker
    from matplotlib import pyplot
    from matplotlib import patches
    from matplotlib.collections import PatchCollection
except ImportError:
    print "Sorry, you don't have the matplotlib module installed."
    print "Please install or reconfigure matplotlib"
    print "and try again."

import math

def augment_range(plot_range):
    """ Adds points around every point in plot_range for accurately plotting integer-based curves """
    a_range = plot_range + [x + 0.0001 for x in plot_range] + [x - 0.0001 for x in plot_range]
    a_range.sort()
    a_range = [x for x in a_range if x >= 0] # clear out negative values

    return a_range

def plot_eta(eta, plot_range, label=None, color=None):
    """ Plot an eta function """
    # range including surroundings of integers to get the steps right
    augmented_range = plot_range + [x + 0.0001 for x in plot_range] + [x - 0.0001 for x in plot_range]
    augmented_range.sort()

    pyplot.plot(augmented_range, [eta(x) for x in augmented_range], label=label, color=color)
    pyplot.xlim(xmin=0)
    pyplot.ylim(ymin=0)
    pyplot.xlabel("$\Delta t$")


def plot_event_model(model, plot_range, file_format=None, separate_plots=True):
    """ Plot the Task's eta and delta_min functions """

    # range including surroundings of integers
    augmented_range = plot_range + [x + 0.0001 for x in plot_range] + [x - 0.0001 for x in plot_range]
    augmented_range.sort()
    w, h = pyplot.figaspect(0.7)
    pyplot.figure(figsize=(w, h))

    if not separate_plots:
        pyplot.subplot(121)
        pyplot.subplots_adjust(left=0.05, bottom=0.1, right=0.97, top=0.92, wspace=None, hspace=None)
    pyplot.plot(augmented_range, [model.eta_plus(x) for x in augmented_range], 'b-^',
                label="$\eta^+(\Delta t)$")
    pyplot.plot(augmented_range, [model.eta_min(x) for x in augmented_range], 'b-v',
                label="$\eta^-(\Delta t)$")
    #pyplot.plot(plot_range,[self.eta(x) for x in plot_range], 'bo',)        
    pyplot.xlim(xmin=0)
    pyplot.ylim(ymin=0)
    pyplot.title("$\eta(\Delta t)$")
    pyplot.xlabel("$\Delta t$")
    pyplot.legend(loc='best')

    if separate_plots and file_format is not None:
            pyplot.savefig("plot-eta." + file_format)

    ## plot delta_min
    if separate_plots:
        pyplot.figure()
    delta_range = list(range(2, max(plot_range)))
    if not separate_plots:
        pyplot.subplot(122)
    pyplot.plot(delta_range, [model.delta_min(x) for x in delta_range], 'v',
                label="$\delta^-(n)$")
    if model.delta_plus(2) < float('inf'):
        # only plot delta+ if it is not infinity
        pyplot.plot(delta_range, [model.delta_plus(x) for x in delta_range], '^',
                    label="$\delta^+(n)$")
    pyplot.xlim(xmin=0)
    pyplot.ylim(ymin=0)
    pyplot.title("$\delta(n)$")
    pyplot.xlabel("n")
    pyplot.legend(loc='best')

    if file_format is not None:
        if separate_plots:
            pyplot.savefig("plot-delta_min." + file_format)
        else:
            pyplot.savefig("plot." + file_format)

def aesthetic_paper_parameters(column_size=252):
    fig_width_pt = column_size  # Get this from LaTeX using \showthe\columnwidth
    inches_per_pt = 1.0 / 72.27               # Convert pt to inch
    golden_mean = (math.sqrt(5) - 1.0) / 2.0         # Aesthetic ratio
    fig_width = fig_width_pt * inches_per_pt  # width in inches
    fig_height = fig_width * golden_mean      # height in inches
    fig_size = [fig_width, fig_height]
    params = {
              'figure.dpi' : 72.27,
              'axes.labelsize': 10,
              'text.fontsize': 10,
              'legend.fontsize': 10,
              'xtick.labelsize': 8,
              'ytick.labelsize': 8,
              'text.usetex': True,
              'figure.figsize': fig_size}
    print params
    return params

def plot_gantt(tasks, file_name=None, show = True, xlim=None,
               preemtion_bar_height=0.2,
               height=1, #height of the box during actual execution
               hdist=1, #vertical distance between two execution bars 
               min_dist_arrows=0.2, # minimum distance between arrows (e.g. in case actications overlap
               plot_event_arrival=True, # plot arrival arrows
               plot_activation_finishing=False, # plot finishing arrows
               annotate_tasks=True, # annotate additional information
               task=None, # the task that should be annotated (draws a WCRT arrow for this task)
               wcrt_voffset=0.5, # amount of vertical distance used for the wcrt arrow
               annotation_offset=0.2, # offset of the annotation (q=1) text
               arrow_width=0.05, # arrow width
               arrow_head_width=0.4,
               arrow_head_length=0.2,
               arrow_yoffset=0.1, # arrow vertical offset
               xticks_only_on_changes=False, # place tick only when events happen
               color_preemtion_bar = '0.30',
               color_execution_bar = 'yellow'):
    """ Plot a gantt chart of a given task list.
        Execution time information is taken from the task attribute q_exec_windows which is written by the simulation framework
    """
    #matplotlib.rcParams.update(aesthetic_paper_parameters(column_size = 2 * 252))

    w, h = pyplot.figaspect(0.4)
    fig = pyplot.figure(figsize=(w * 0.5, h * 0.5))
    ax = fig.add_subplot(111)

    ypos = 0
    yticks = list()
    xticks = set()
    #arrows = list()

    for t in tasks:

        parts = list()

        yticks.append(ypos) # append a y-tick, so we see a dashed line here

        if not hasattr(t, 'q_exec_windows'):
            print "task %s has no q_exec_windows assigned! use simulation.py to simulate the CI" % t.name
            exit(-1)

        # broken bar segments
        for part in t.q_exec_windows:
            parts += part

        print "orig parts", t.name, parts
        print "orig execwindows", t.q_exec_windows, parts

        if len(parts) == 0:
            ypos -= (hdist + height)
            continue

        # Draw bar segments
        parts = [(p[0], p[1] - p[0]) for p in parts] # transform coordinates to the form (start, length)

        for p in parts:
            xticks.add(p[0])
            xticks.add(p[1])




        # draw the bars verically aligned to ypos, so that ypos is the middle of the bar
        ax.broken_barh(parts,
                       (ypos - height / 2. , height),
                       facecolors=color_execution_bar,
                       alpha=1)

        # draw preemtion times, activation and response time arrows
        xposshift = 0
        for q in range(0, len(t.q_exec_windows)):
            #draw actication arrows
            xpos = t.in_event_model.delta_min(q + 1)

            #draw the the preemption bars


            print t.q_exec_windows[q]
            task_activity_end = t.q_exec_windows[q][-1][1]

            ax.broken_barh([(xpos, task_activity_end - xpos)],
                           (ypos - preemtion_bar_height / 2. , preemtion_bar_height),
                           facecolors=color_preemtion_bar,
                           edgecolor=color_preemtion_bar,
                           alpha=1,
                           zorder=0)

            # check if there are multiple activations right after each other
            # we don't want them to overlap, s
            if q >= 1:
                if abs(xpos - t.in_event_model.delta_min(q)) < min_dist_arrows:
                    xposshift += min_dist_arrows
                else:
                    xposshift = 0.0

            if plot_event_arrival == True:
                # Draw activation times
                activation_arrow = patches.FancyArrow(xpos + xposshift, ypos + arrow_yoffset,
                                                      0, height / 2. ,
                                                      length_includes_head=True,
                                                      width=arrow_width,
                                                      head_width=arrow_head_width,
                                                      head_length=arrow_head_length,
                                                      facecolor='black',
                                                      alpha=1)
                ax.add_patch(activation_arrow)

            if plot_activation_finishing == True:
                # Draw finishing times
                q_wcrt = t.q_exec_windows[q][-1][1]
                response_arrow = patches.FancyArrow(q_wcrt, ypos - arrow_yoffset,
                                                    0, -height / 2. ,
                                                    length_includes_head=True,
                                                    width=arrow_width,
                                                    head_width=arrow_head_width,
                                                    head_length=arrow_head_length,
                                                    facecolor='black',
                                                    alpha=1)
                ax.add_patch(response_arrow)

            if annotate_tasks == True and (task and task == t):
                first_segment = t.q_exec_windows[q][0][0]

                text = '$q=%d$' % (q + 1)
                #if (annotate_wcrt and annotate_wcrt != t):
                #    text = '$t=%.0f$' % (first_segment)


                #ax.text(first_segment + annotation_offset, ypos + height / 2. + annotation_offset, text,
                #     horizontalalignment = 'left',
                #     verticalalignment = 'bottom')

                ax.text(first_segment + annotation_offset, ypos - height / 2., text,
                     horizontalalignment='left',
                     verticalalignment='bottom')

            if task and task == t:
                wcrt_start = t.in_event_model.delta_min(t.q_max)
                wcrt_end = t.wcrt + wcrt_start
                annotation_ypos = ypos - height / 2. - wcrt_voffset
                wcrt_arrow = patches.FancyArrowPatch((wcrt_start, annotation_ypos),
                                                     (wcrt_end, annotation_ypos),
                                                      arrowstyle="<->", mutation_scale=20.)
                ax.add_patch(wcrt_arrow)

                ax.text(wcrt_start + t.wcrt / 2., annotation_ypos, 'WCRT=%f' % (t.wcrt),
                        horizontalalignment='center',
                        verticalalignment='center',
                        backgroundcolor='white')



        ypos -= (hdist + height)

    xticks = sorted(list(xticks))

    ax.set_xlabel('time $\Delta t$')
    ax.set_yticks(yticks) # add the ypos markers for each task

    if xticks_only_on_changes == True:
        ax.set_xticks(xticks)
    else:
        ax.xaxis.set_major_locator(ticker.MaxNLocator(20, steps=[1, 2, 5]))

    ax.set_yticklabels([t.name for t in tasks]) # set tasknames
    ax.autoscale_view(tight=True, scalex=True, scaley=True) # autoscale first
    ax.set_ylim(ypos + hdist + height / 2. , height) # set ylim manual
    if xlim:
        ax.set_xlim(-arrow_head_width, xlim)
    ax.grid(True)

    if file_name is not None:
        pyplot.savefig(file_name, bbox_inches='tight')

    if show:
        pyplot.show()


