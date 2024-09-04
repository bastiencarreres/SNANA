#!/usr/bin/env python
#
# Created Sep 2024 by R.Kessler
#
# For input simlib_file, produce monitor plots.
# If input simlib file has name baseline_v3.4_10yrs.simlib,
# produce output file baseline_v3.4_10yrs.pdf.
#
# =======================

import os, sys, argparse, gzip, logging, shutil, time, math, subprocess, yaml, glob
from argparse import Namespace


PREFIX_TEMP_FILES  = "TEMP_PLOT_SIMLIB"  # to easily identify and remove temp files
PROGRAM_SIM        = "snlc_sim.exe"      # SNANA code
PROGRAM_PLOT_TABLE = "plot_table.py"     # SNANA code
PROGRAM_COMBINE    = "convert"           # linux command
PLOT_SUFFIX        = "png"

WILDCARD_PLOTS    = f"{PREFIX_TEMP_FILES}*.{PLOT_SUFFIX}"
WILDCARD_LOGS     = f"{PREFIX_TEMP_FILES}*.LOG"

STRING_AVG = "AVG"
STRING_OBS = "OBS"

STRING_FIRST = "FIRST"
STRING_LAST  = "LAST"

MARKER_LIST = [ 's' , '+', 'o', 'x', '^', 'v', 'd', '4' ]

# ============================
def setup_logging():

    #logging.basicConfig(level=logging.DEBUG,
    logging.basicConfig(level=logging.INFO,
        format="[%(levelname)8s]  %(message)s")
    #format="[%(levelname)8s |%(filename)21s:%(lineno)3d]   %(message)s")    

    logging.getLogger("matplotlib").setLevel(logging.ERROR)
    logging.getLogger("seaborn").setLevel(logging.ERROR)

    return  # end setup_logging

def get_args():
    parser = argparse.ArgumentParser()

    msg = "name of simlib/cadence file to read and make plots"
    parser.add_argument("-s", "--simlib_file", help=msg, type=str, default=None)

    msg = "mjd min max binsize"
    parser.add_argument("--mjd_range", help=msg, nargs="+", default=None)

    msg = f"do NOT remove temporary {PREFIX_TEMP_FILES}* files (for debugging)"
    parser.add_argument("--noclean", help=msg, default=False)    

    # parse it
    args = parser.parse_args()

    #if len(sys.argv) == 1:
    #    parser.print_help()
    #    sys.exit()

    return args
    # end get_args


def get_simlib_dump_file_names(simlib_file):
    base          = os.path.basename(simlib_file).split('.')[0]
    dump_file_avg = f"SIMLIB_DUMP_AVG_{base}.TEXT"
    dump_file_obs = f"SIMLIB_DUMP_OBS_{base}.TEXT"    
    return dump_file_avg, dump_file_obs

def get_next_plot_filename(plot_info, dump_type):
    # dump_type = AVG or OBS
    plot_info.plotnum += 1
    plot_file = f"{PREFIX_TEMP_FILES}_{plot_info.plotnum:03d}_{dump_type}.{PLOT_SUFFIX}"
    log_file  = f"{PREFIX_TEMP_FILES}_{plot_info.plotnum:03d}_{dump_type}.LOG"    
    return plot_file, log_file
    
def prepare_simlib_dump(args, plot_info):
    # If SIMLIB-DUMP files already exit with unix time stamp later
    # than simlib file --> do nothing;
    # else use snlc_sim.exe to create the DUMP files.

    simlib_file = os.path.expandvars(args.simlib_file)
    
    dump_file_avg, dump_file_obs = get_simlib_dump_file_names(simlib_file)

    
    dump_file_list = [ dump_file_avg, dump_file_obs ]
    logging.info(f"Check for SIMLIB dump files: {dump_file_list}")
    
    create_dump_files = False
    tstamp_simlib     = os.path.getmtime(simlib_file)
    
    for dump_file in dump_file_list:
        if not os.path.exists(dump_file):
            create_dump_files = True ;  break

        tstamp_dump = os.path.getmtime(dump_file)
        if tstamp_dump < tstamp_simlib:
            create_dump_files = True ;  break
        
    if create_dump_files:
        logging.info(f"Run {PROGRAM_SIM} to create dump files from {args.simlib_file}")
        logging.info(f"... please be patient ... ")
        log_file = f"{PREFIX_TEMP_FILES}_make_dump_files.log"
        command = f"{PROGRAM_SIM} NOFILE SIMLIB_FILE {simlib_file} SIMLIB_DUMP 3 >& {log_file} "
        ret = subprocess.run( [ command ], cwd=os.getcwd(),
                             shell=True, capture_output=False, text=True )

    else:
        logging.info(f"Use existing dump files.")


    # - - - -
    # read DOCUMENTATION block from AVG file, which has things like SURVEY and FILTERS
    # dump_file_list[0]
    with open(dump_file_list[0] ) as f:
        docana_yaml = yaml.safe_load(f.read())['DOCUMENTATION']

    plot_info.dump_file_avg = dump_file_avg
    plot_info.dump_file_obs = dump_file_obs
    plot_info.dump_file_avg = dump_file_avg
    plot_info.docana_yaml   = docana_yaml
    
    return # end prepare_simlib_dump

def clean_temp_files():
    wildcard = f"{PREFIX_TEMP_FILES}*"
    temp_file_list = glob.glob(f"{wildcard}")
    if len(temp_file_list) > 0:
        cmd_rm = f"rm {wildcard}"
        os.system(cmd_rm)        
    return
    
def prepare_plot_table_AVG_illum(args, plot_info):

    xvar   = 'RA'
    yvar   = 'cos((DEC+90)*.01745)'
    xlabel = 'RA (deg)'
    ylabel = 'cos(DEC+90)'

    cmd_first = command_append_auto(STRING_FIRST, plot_info, STRING_AVG)
    cmd_last  = command_append_auto(STRING_LAST,  plot_info, STRING_AVG)    
    
    cmd = \
        f"{cmd_first} " + \
        f"@V '{xvar}:{yvar}' " + \
        f"@@TITLE 'SIMLIB Sky Coverage' " + \
        f"@@XLABEL '{xlabel}' " + \
        f"@@YLABEL '{ylabel}' " + \
        f"{cmd_last}"
        
    return cmd   # end prepare_plot_table_AVG_illum

def prepare_plot_table_AVG1D(args, plot_info, var, label):

    # overlay [var]_band on one plot
    docana_yaml  = plot_info.docana_yaml
    filter_list  = list(docana_yaml['FILTERS'])
    survey       = docana_yaml['SURVEY']

    cmd_first = command_append_auto(STRING_FIRST, plot_info, STRING_AVG)
    cmd_last  = command_append_auto(STRING_LAST,  plot_info, STRING_AVG)

    cmd_var    = '@V '
    cmd_legend = '@@LEGEND '
    for band in filter_list:
        cmd_var    += f"{var}_{band} "
        cmd_legend += "{band} "
        
    cmd = f"{cmd_first} "
    cmd += f"{cmd_var} "
    cmd += f"{cmd_legend} "
    cmd += f"@@XLABEL '{label}' "
    cmd += f"@@TITLE '{var} for {survey}' "
    cmd += f"@@OPT HIST "
    cmd += f"{cmd_last}"

    return cmd   # end prepare_plot_table_AVG1D


def prepare_plot_table_OBS(args, plot_info, var, label):

    cmd_list = []

    docana_yaml  = plot_info.docana_yaml
    filter_list  = list(docana_yaml['FILTERS'])
    nfilt        = len(filter_list)
    survey       = docana_yaml['SURVEY']
    marker_list  = MARKER_LIST[0:nfilt]
    
    cmd_first = command_append_auto(STRING_FIRST, plot_info, STRING_OBS)
    cmd_last  = command_append_auto(STRING_LAST,  plot_info, STRING_OBS)

    # - - - - - -
    # first generate single 2D plot of val vs. MJD with all bands overlaid on same plot
    cmd_cut    = '@@CUT '
    cmd_legend = '@@LEGEND '
    cmd_marker = '@@MARKER '
    for band, mk in zip(filter_list, marker_list):
        cmd_cut += f'\'BAND=\"{band}\"\' '
        cmd_legend += f"{band} "
        cmd_marker += f"{mk} "

    cmd  = f"{cmd_first}  "
    cmd += f"@V MJD:{var} "
    cmd += f"{cmd_cut} "
    cmd += f"{cmd_legend} "
    cmd += f"{cmd_marker} "    
    cmd += f"@@YLABEL '{label}' "
    cmd += f"@@TITLE '{var} for {survey}' "
    cmd += f"@@ALPHA 0.0 "
    cmd += f"@@OPT GRID MEDIAN "
    cmd += f"{cmd_last}"
    cmd_list.append(cmd)

    # next generate separate 2D plot (val vs. MJD) for each band
    for band in filter_list:
        cmd_first = command_append_auto(STRING_FIRST, plot_info, STRING_OBS)
        cmd_last  = command_append_auto(STRING_LAST,  plot_info, STRING_OBS)
        cut  = f'BAND="{band}"'
        cmd  = f"{cmd_first}  "
        cmd += f"@V MJD:{var} "
        cmd += f"@@CUT \"BAND=\'{band}\'\"  "
        cmd += f"@@YLABEL '{label}' "
        cmd += f"@@TITLE '{var} for {survey} {band}-band' "
        cmd += f"@@ALPHA 0.3 "
        cmd += f"@@OPT GRID MEDIAN "
        cmd += f"{cmd_last}"
        cmd_list.append(cmd)
    
    
    return cmd_list   # end prepare_plot_table_OBS


def command_append_auto(which_command, plot_info, which_dump):
    cmd = None
    if which_command == STRING_FIRST :
        if which_dump == STRING_AVG:        
            dump_file = plot_info.dump_file_avg
        else:
            dump_file = plot_info.dump_file_obs 
        cmd = f"{PROGRAM_PLOT_TABLE} @@TFILE {dump_file} "
    elif which_command == STRING_LAST :
        save_file, log_file  = get_next_plot_filename(plot_info, which_dump)
        cmd = f"@@SAVE {save_file}   >& {log_file} & "
        
    return cmd
        

def get_save_arg(plot_info):
    save_file =  get_next_plot_filename(plot_info)
    arg       =  f"@@SAVE {save_file}"
    return arg

def prepare_plot_table_commands(args, plot_info):

    # main driver to prepare string for each plot_table command
    command_list = []

    # - - - - - - - - - - -- - 
    # plots fro AVG dump
    command = prepare_plot_table_AVG_illum(args, plot_info)
    command_list.append(command)

    VARLIST_AVG = {
        'N'  :     "Nobs", 
        'ZPT':     "ZPT (ADU)" ,
        'PSF':     "PSF-sigma (pixels)",
        'M5SIG':   "$m_{5\sigma}$"
    }

    for var, label in VARLIST_AVG.items():
        full_label = f"average {label} per sky location"
        command = prepare_plot_table_AVG1D(args, plot_info, var, full_label)
        command_list.append(command)

    # - - - - - - - -
    # plots from OBS dump

    VARLIST_OBS = {
        'ZP_pe'  :   "ZP (pe)" ,
        'SKYMAG' :   "SkyMag/arcsec^2" ,
        'PSF'    :   "PSF-sigma (pixels)",
        'M5SIG'  :   "$m_{5\sigma}$"
    }

    for var, label in VARLIST_OBS.items():
        cmd_list = prepare_plot_table_OBS(args, plot_info, var, label)
        command_list += cmd_list
    
    return command_list   # end prepare_plot_table_commands


def execute_plot_commands(plot_command_list):

    nplot_per_group = 6
    t_delay         = 5.0  # sleep time between launch next group
    n_plot = 0
    for plot_command in plot_command_list:
        n_plot += 1
        logging.info(f"Launch plot command {n_plot}: \n\t {plot_command}")
        os.system(plot_command)
        if n_plot % nplot_per_group == 0:  time.sleep(t_delay)
        
    return  # end execute_plot_commands

def wait_for_plots(args, plot_info):

    t_wait = 3.0  # wait time bewteen each check
    
    n_log_expect   = len(plot_info.plot_command_list)
    n_log_file     = 0
    while n_log_file < n_log_expect:
        log_file_list = glob.glob(f"{WILDCARD_LOGS}")
        n_log_file    = len(log_file_list)
        logging.info(f"Found {n_log_file} {WILDCARD_LOGS} files out of {n_log_expect}")
        time.sleep(t_wait)

    # check if all plot files exist
    n_plot_file    = 0
    t_wait_tot     = 0
    while n_plot_file < n_log_expect and t_wait_tot < 20 :
        plot_file_list = glob.glob(f"{WILDCARD_PLOTS}")
        n_plot_file    = len(plot_file_list)
        logging.info(f"Found {n_plot_file} {PLOT_SUFFIX} files (expect {n_log_expect}) ")
        time.sleep(t_wait)
        t_wait_tot += t_wait
        
    if n_plot_file == n_log_expect:
        pass
    else:
        pass
    
    #ret = subprocess.run( [ command ], cwd=os.getcwd(),
    #                      shell=True, capture_output=False, text=True )
    
    return # end wait_for_plots

def combine_all_plots(args, plot_info):

    # check if combine program is available
    rc = subprocess.call(['which', PROGRAM_COMBINE , '2>/dev/null' ] )
    
    if rc == 0:
        base          = os.path.basename(simlib_file).split('.')[0]
        pdf_file    = f"{base}.pdf"
        cmd_combine = f"{PROGRAM_COMBINE}  {WILDCARD_PLOTS} > {pdf_file}"
        os.system(cmd_combine)
        return True
    else:
        logging.warning(f"{PROGRAM_COMBINE} program does not exist; " \
                        f"cannot combine plots into a single PDF file")

    return  False # end combine_all_plots

# ===================================================
if __name__ == "__main__":
    
    setup_logging()
    logging.info("# ========== BEGIN plot_simlib ===============")
    args   = get_args()
    
    clean_temp_files()
    
    plot_info = Namespace()
    plot_info.plotnum = 0

    prepare_simlib_dump(args, plot_info)

    # prepare all of the plot_table commands, but don't plot anything [yet]
    plot_info.plot_command_list = prepare_plot_table_commands(args, plot_info)

    # execute plot_table commands
    execute_plot_commands(plot_info.plot_command_list)

    # wait for everything to finish
    wait_for_plots(args, plot_info)

    # combine all plots into single pdf file
    do_combine = combine_all_plots(args, plot_info)

    # clean up mess
    if do_combine and not args.noclean:
        clean_temp_files()

    logging.info(f"Done.")
    
    # == END: ===
