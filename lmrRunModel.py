# Standard Python Libraries
from __future__ import division
import os
import shutil
import sys
import subprocess
import fileinput
import glob
import copy

# Python lXML - http://lxml.de/
have_lxml = True
try:
    from lxml import etree as ElementTree
    import lxml
except ImportError:
    have_lxml = False
    print ('=== WARNING ===\n Unable to find the Python library lxml. The LMR can still run, '
           'but will not be able to validate the lmrStart.xml file. You can obtain it from: '
           'http://lxml.de/, or from your package manager.')
    from xml.etree import cElementTree as ElementTree


def load_xml(input_xml='lmrStart.xml', xsd_location='LMR.xsd'):
    """
    ===== xml2dict =================
    Author:  Duncan McGreggor
    License: PSF License
    Website: http://code.activestate.com/recipes/410469-xml-as-dictionary/
    """
    class XmlListConfig(list):
        def __init__(self, aList):
            for element in aList:
                if element:
                    if len(element) == 1 or element[0].tag != element[1].tag:
                        self.append(XmlDictConfig(element))
                    elif element[0].tag == element[1].tag:
                        self.append(XmlListConfig(element))
                elif element.text:
                    text = element.text.strip()
                    if text:
                        self.append(text)

    class XmlDictConfig(dict):
        def __init__(self, parent_element):
            if parent_element.items():
                self.update(dict(parent_element.items()))
            for element in parent_element:
                if len(element):
                    if len(element) == 1 or element[0].tag != element[1].tag:
                        new_dict = XmlDictConfig(element)
                    else:
                        new_dict = {element[0].tag: XmlListConfig(element)}
                    if element.items():
                        new_dict.update(dict(element.items()))
                    self.update({element.tag: new_dict})
                elif element.items():
                    self.update({element.tag: dict(element.items())})
                else:
                    self.update({element.tag: element.text.strip()})  # Line modified by LMondy to strip
    """
    ===== end of xml2dict =================
    """

    if have_lxml:
        try:
            tree = ElementTree.parse(input_xml)
            schema = ElementTree.XMLSchema(file=xsd_location)
            schema.validate(tree)               # Validate against xsd.
            error_log = schema.error_log
        except lxml.etree.XMLSyntaxError as e:
            error_log = "=== ERROR ===\nThere was an issue reading in the XML file {input_xml}.\n".format(input_xml=input_xml)
            for i, r in enumerate(e.error_log):
                error_log = '\n'.join([error_log,
                                    ('Problem {errornum}:\nThe code is reporting that on line {line} this error occured:'
                                     '\n\t\"{message}\"\n'.format(errornum=i+1, line=r.line, message=r.message))])
            error_log = '\n'.join([error_log,
                                ('Please have a look at {input_xml} closely, especially around the mentioned lines. '
                                 'If you are still having issues, try using an XML validator online to see where the bug is.\n'.format(input_xml=input_xml))])
            raise ValueError(error_log)  # Make this an LMR exception
        except lxml.etree.XMLSchemaParseError as e:
            print ("=== WARNING ===\nProblem with the XSD validation! Computer says: \n\t{schema_error}\n"
                   "The LMR will still try to run, but will be unable to check that {input_xml} is all"
                   " OK. If you are having problems, try to download the LMR.xsd file again and put it "
                   "in this folder, or use an online XML validator on the {input_xml} file.").format(schema_error=e, input_xml=input_xml)
        except Exception as e:
            raise Exception("=== ERROR ===\nA serious and unexpected error has occured. Perhaps try getting a fresh copy of the LMR, and try again.")
    else:
        try:
            tree = ElementTree.parse(input_xml)     # Any errors from mismatching tags will be caught
        except Exception as e:
            error_log = ("=== ERROR ===\nThere was an issue reading in the XML file {input_xml}.\n"
                         "The code is reporting that:\n\t{xmlerror}\n"
                         "Please have a look at {input_xml} closely, especially around the mentioned lines. "
                         "If you are still having issues, try using an XML validator online to see where the bug is.\n").format(input_xml=input_xml, xmlerror=e)
            raise ValueError(error_log)

    root = tree.getroot()
    return XmlDictConfig(root)


def process_xml(raw_dict):

    def xmlbool(xml_bool_string):
        return xml_bool_string == "true"  # Don't need to worry about capitals - XML parser would catch it before now

    # Initialise some standard stuff
    model_dict = {"input_xmls":               "{xmls_dir}/lmrMain.xml",
                  "model_resolution":         {},
                  "thermal_model_resolution": {}}

    command_dict = {"input_xmls":               "{input_xmls}",
                    "resolution":               ("--elementResI={resolution[x]} "
                                                 "--elementResJ={resolution[y]} "
                                                 "--elementResK={resolution[z]}"),
                    "dims":                     "--dim={dims}",
                    "output_path":              "--outputPath={output_path}",
                    "output_pictures":          "--components.window.Type=DummyComponent",
                    "max_time":                 "--end={max_time}",
                    "max_timesteps":            "--maxTimeSteps={max_timesteps}",
                    "checkpoint_every_x_years": "--checkpointAtTimeInc={checkpoint_every_x_years}",
                    "checkpoint_every_x_steps": "--checkpointEvery={checkpoint_every_x_steps}",
                    "uwbinary":                 "{uwbinary}",
                    "parallel_runner":          "{parallel_command}", }

    # <Output_Controls>
    output_controls = raw_dict["Output_Controls"]

    model_dict["description"] = output_controls["description"]

    for dim in output_controls["model_resolution"].keys():
        model_dict["model_resolution"][dim] = int(output_controls["model_resolution"][dim])

    experiment_duration_options = output_controls["experiment_duration_options"]
    model_dict["max_timesteps"] = int(experiment_duration_options["maximum_timesteps"])
    model_dict["max_time"] = float(experiment_duration_options["maximum_time_in_years"])

    checkpoint_frequency_options = output_controls["checkpoint_frequency_options"]
    model_dict["checkpoint_every_x_years"] = float(checkpoint_frequency_options["every_x_years"])
    model_dict["checkpoint_every_x_steps"] = int(checkpoint_frequency_options["every_x_timesteps"])

    model_dict["output_pictures"] = xmlbool(output_controls["output_pictures"])
    model_dict["write_log_file"] = xmlbool(output_controls["write_log_file"])
    # </Output_Controls>


    # <Thermal_Equilibration>
    therm_equil = raw_dict["Thermal_Equilibration"]

    model_dict["run_thermal_equilibration_phase"] = xmlbool(therm_equil["run_thermal_equilibration_phase"])
    model_dict["update_xml_information"] = xmlbool(therm_equil["update_xml_information"])
    model_dict["preserve_thermal_checkpoints"] = xmlbool(therm_equil["preserve_thermal_equilibration_checkpoints"])

    thermal_output_controls = therm_equil["output_controls"]

    model_dict["thermal_description"] = thermal_output_controls["description"]

    for dim in thermal_output_controls["thermal_model_resolution"].keys():
        model_dict["thermal_model_resolution"][dim] = int(thermal_output_controls["thermal_model_resolution"][dim])

    experiment_duration_options = thermal_output_controls["experiment_duration_options"]
    model_dict["thermal_max_timesteps"] = int(experiment_duration_options["maximum_timesteps"])
    model_dict["thermal_max_time"] = float(experiment_duration_options["maximum_time_in_years"])

    checkpoint_frequency_options = thermal_output_controls["checkpoint_frequency_options"]
    model_dict["thermal_checkpoint_every_x_years"] = float(checkpoint_frequency_options["every_x_years"])
    model_dict["thermal_checkpoint_every_x_steps"] = int(checkpoint_frequency_options["every_x_timesteps"])
    # </Thermal_Equilibration>


    # <Restarting_Controls>
    restarting = raw_dict["Restarting_Controls"]
    model_dict["restarting"] = xmlbool(restarting["restart"])
    if model_dict["restarting"]:
        try:
            # This is an optional keyword, so if it's not there, use -1
            model_dict["restart_timestep"] = int(restarting["restart_from_step"])
        except KeyError:
            model_dict["restart_timestep"] = -1
        command_dict["restart"] = "--restartTimestep={restart_timestep}"
    # </Restarting_Controls>


    # <Solver_Details>
    solverdetails = raw_dict["Solver_Details"]
    for solver in ["linear_solver", "nonLinear_solver"]:
        prefix = solver.split("_")[0]
        model_dict[solver] = {"tolerance":    float(solverdetails[solver]["tolerance"]),
                              "min_iterations": int(solverdetails[solver]["min_iterations"]),
                              "max_iterations": int(solverdetails[solver]["max_iterations"])}

        if model_dict["run_thermal_equilibration_phase"] and prefix == "nonLinear":
            model_dict[solver]["max_iterations"] = 1   # So UW doesn't try to nonLinearly solve pure diffusion

        command_dict[solver] = ("--{solver}Tolerance={tolerance} "
                                "--{solver}MinIterations={min_iterations} "
                                "--{solver}MaxIterations={max_iterations}"
                                .format(solver=prefix,
                                        tolerance=model_dict[solver]["tolerance"],
                                        min_iterations=model_dict[solver]["min_iterations"],
                                        max_iterations=model_dict[solver]["max_iterations"]))

    model_dict["force_multigrid_level_to_be"] = int(solverdetails["force_multigrid_level_to_be"])
    model_dict["force_direct_solve"] = xmlbool(solverdetails["force_direct_solve"])
    model_dict["force_multigrid_solve"] = xmlbool(solverdetails["force_multigrid_solve"])

    if model_dict["force_multigrid_solve"] and model_dict["force_direct_solve"]:
        raise ValueError("=== ERROR ===\nYou cannot force a direct solve and also force a multigrid solve. Please check the <Solver"
                         "_Details> part of your lmrStart.xml.")
    # </Solver_Details>


    # <Underworld_Execution>
    uw_exec = raw_dict["Underworld_Execution"]
    if os.path.exists(uw_exec["Underworld_binary"]):
        model_dict["uwbinary"] = uw_exec["Underworld_binary"]
    else:
        raise ValueError("=== ERROR ===\nThe path to the Underworld binary doesn't exist. You specified: {0}".format(uw_exec["Underworld_binary"]))

    model_dict["uw_root"] = os.path.split(os.path.split(os.path.dirname(uw_exec["Underworld_binary"]))[0])[0]
    # The worst command ever - essentially, go up 2 directories.

    try:
        model_dict["parallel_command"] = uw_exec["parallel_command"]
    except KeyError:
        model_dict["parallel_command"] = "mpirun"

    try:
        model_dict["parallel_command_cpu_flag"] = uw_exec["parallel_command_cpu_flag"]
    except KeyError:
        model_dict["parallel_command_cpu_flag"] = "-np"

    if xmlbool(uw_exec["supercomputer_mpi_format"]) is False:
        model_dict["cpus"] = uw_exec["CPUs"]
        command_dict["parallel_runner"] = "{parallel_command} {parallel_command_cpu_flag} {cpus}"

    try:
        model_dict["extra_command_line_flags"] = uw_exec["extra_command_line_flags"]
    except KeyError:
        model_dict["extra_command_line_flags"] = ""
    command_dict["extra_command_line_flags"] = "{extra_command_line_flags}"

    try:
        model_dict["verbose_run"] = xmlbool(uw_exec["verbose_run"])
    except KeyError:
        model_dict["verbose_run"] = False
    # </Underworld_Execution>

    return model_dict, command_dict


def get_textual_resolution(res):
    """
    Return a string of the resolution with x's between.
    """
    return "x".join(map(str, (res["x"],
                              res["y"],
                              res["z"])))


def prepare_job(model_dict, command_dict):
    """
    Prepare output paths, resolutions, and special functions for thermal equilibration.
    """
    if model_dict["model_resolution"]["z"] <= 0:
        model_dict["dims"] = 2
        model_dict["thermal_model_resolution"]["z"] = 0  # Just to be sure.
    else:
        if model_dict["thermal_model_resolution"]["z"] <= 0:
            raise ValueError("You have asked for a 3D model in <model_resolution>, but only a 2D model"
                             " in the <thermal_equilibration> section.")
        model_dict["dims"] = 3

    text_res = get_textual_resolution(model_dict["model_resolution"])
    therm_text_res = get_textual_resolution(model_dict["thermal_model_resolution"])

    model_dict["nice_description"] = "_".join([text_res, model_dict["description"]])
    model_dict["nice_thermal_description"] = "_".join([therm_text_res, model_dict["thermal_description"]])

    model_dict["model_output_path"] = os.path.join(os.getcwd(), "result_{model_description}".format(model_description=model_dict["nice_description"]))
    model_dict["thermal_output_path"] = os.path.join(os.getcwd(), "initial-condition_{thermal_description}".format(thermal_description=model_dict["nice_thermal_description"]))

    cp = copy.deepcopy
    if model_dict["run_thermal_equilibration_phase"]:
        model_dict["resolution"] = cp(model_dict["thermal_model_resolution"])
        model_dict["input_xmls"] += " {xmls_dir}/lmrThermalEquilibration.xml"
        model_dict["output_path"] = cp(model_dict["thermal_output_path"])

        model_dict["checkpoint_every_x_steps"] = cp(model_dict["thermal_checkpoint_every_x_steps"])
        model_dict["checkpoint_every_x_years"] = cp(model_dict["thermal_checkpoint_every_x_years"])

        model_dict["max_timesteps"] = cp(model_dict["thermal_max_timesteps"])
        model_dict["max_time"] = cp(model_dict["thermal_max_time"])

        model_dict["logfile"] = "log_initial-condition_{thermal_description}.txt".format(thermal_description=model_dict["nice_thermal_description"])
    else:
        model_dict["resolution"] = copy.deepcopy(model_dict["model_resolution"])
        model_dict["output_path"] = copy.deepcopy(model_dict["model_output_path"])
        model_dict["logfile"] = "log_result_{model_description}.txt".format(model_description=model_dict["nice_description"])


    # Select solvers
    smaller_model = model_dict["resolution"]["x"] * model_dict["resolution"]["y"] < 1e6

    if (((model_dict["dims"] == 2 and smaller_model) or model_dict["force_direct_solve"])
         and not model_dict["force_multigrid_solve"] or model_dict["run_thermal_equilibration_phase"]):
        print "SOLVERS: using MUMPS"

        solvers = ["-Uzawa_velSolver_pc_factor_mat_solver_package mumps",
                   "-mat_mumps_icntl_14 200",
                   "-Uzawa_velSolver_ksp_type preonly",
                   "-Uzawa_velSolver_pc_type lu",
                   "-log_summary",
                   "-options_left"]

    else:
        print "SOLVERS: using Multigrid"

        def multigrid_test(number):
            if number == 0:
                return 1e10  # Bit of a hack, but if one of the numbers is 0, then return a really big number.
            count = 1
            while number % 2.0 == 0:
                number = number / 2.0
                count += 1
            return count

        max_mg_level = min(multigrid_test(model_dict["resolution"]["x"]),
                           multigrid_test(model_dict["resolution"]["y"]),
                           multigrid_test(model_dict["resolution"]["z"]))

        if model_dict["force_multigrid_level_to_be"] > 0:
            if max_mg_level >= model_dict["force_multigrid_level_to_be"]:
                model_dict["mg_levels"] = model_dict["force_multigrid_level_to_be"]
            else:
                ValueError("=== ERROR ===\nYou have forced the multigrid level to be too high. The max calculated is {maxmg}.".format(maxmg=max_mg_level))
        else:
            model_dict["mg_levels"] = max_mg_level

        """
         # Old solver setups
        solvers = ["--mgLevels=4",
                   "-ksp_type fgmres",
                   "-mg_levels_pc_type bjacobi",
                   "-mg_levels_ksp_type gmres",
                   "-mg_levels_ksp_max_it 3",
                   "-mg_coarse_pc_factor_mat_solver_package superlu_dist",
                   "-mg_coarse_pc_type lu",
                   "-log_summary",
                   "-options_left"]

        solvers = ["-pc_mg_type full -ksp_type richardson -mg_levels_pc_type bjacobi",
                   "-mg_levels_ksp_type gmres -mg_levels_ksp_max_it 3",
                   "-mg_coarse_pc_factor_mat_solver_package superlu_dist -mg_coarse_pc_type lu",
                   "-pc_mg_galerkin -pc_mg_levels 5 -pc_type mg",
                   "-log_summary  -pc_mg_log -ksp_monitor_true_residual -options_left -ksp_view",
                   "-ksp_max_it 30",
                   "-options_left"]

        solvers = ["--mgLevels={mg_levels}",
                   "-mg_coarse_pc_factor_mat_solver_package superlu_dist",
                   "-mg_coarse_pc_type lu",
                   "-A11_ksp_type fgmres",
                   "-A11_ksp_monitor",
                   "-A11_pc_mg_smoothup 10",
                   "-A11_pc_mg_smoothdown 10",
                   "-mg_levels_ksp_rtol 1.0e-15",
                   #"-mg_levels_ksp_max_it 5",
                   "-mg_levels_ksp_type minres",
                   "-mg_levels_pc_type sor",
                   "-mg_levels_ksp_convergence_test skip",
                   "-options_left",
                   "-log_summary"]
        """
        solvers = ["--mgLevels={mg_levels}",
                   "-mg_coarse_pc_factor_mat_solver_package mumps",
                   "-mg_coarse_pc_type lu",
                   "-mg_coarse_ksp_type preonly",
                   "-A11_pc_mg_smoothup 2",
                   "-A11_pc_mg_smoothdown 2",
                   "-A11_ksp_monitor",
                   "-options_left",
                   "-log_summary"]


        model_dict["input_xmls"] += " {uw_root}/StgFEM/Apps/src/MultigridForRegular.xml"

    command_dict["solver"] = " ".join(solvers)


    # Prepare file system for UW run.
    output_dir = model_dict["output_path"]
    xmls_dir = os.path.join(output_dir, "xmls/")  # Standard place

    if not os.path.isdir(output_dir):
        os.mkdir(output_dir)

    if model_dict["restarting"]:
        if model_dict["restart_timestep"] == -1:
            # If no restart timestep is specified, automatically find the last one.
            model_dict["restart_timestep"] = find_last_timestep(model_dict["output_path"])
        else:
            last_timestep = find_last_timestep(model_dict["output_path"])
            if last_timestep != model_dict["restart_timestep"]:
                raise ValueError("You have asked to restart the model at timestep {}, but "
                                 "there is no checkpoint of that number".format(model_dict["restart_timestep"]))

        # When we restart, we need to preserve the original XMLs stored in result/xmls.
        # To do so, find the last xmls folder, and increment the number.
        xml_folders = sorted([folder for folder in glob.glob(os.path.join(output_dir, "xmls*"))
                             if os.path.isdir(os.path.join(output_dir, folder))])
        if len(xml_folders) > 1:
            last_restart_num = int(xml_folders[-1].split("_")[-1])
            xmls_dir = os.path.join(output_dir, "xmls_restart_{0}".format(last_restart_num + 1))
        elif len(xml_folders) == 1:
            xmls_dir = os.path.join(output_dir, "xmls_restart_1")

    if not os.path.isdir(xmls_dir):
        os.mkdir(xmls_dir)
    for files in os.listdir("./"):
        if files.endswith(".xml"):
            shutil.copy(files, xmls_dir)

    model_dict["input_xmls"] = model_dict["input_xmls"].format(xmls_dir=xmls_dir, uw_root=model_dict["uw_root"])


    # Need to modify the XML in the result/xmls/folder, so the main folder is pristine.
    if model_dict["run_thermal_equilibration_phase"] is False and model_dict["update_xml_information"] is True:
        last_ts = find_last_timestep(model_dict["thermal_output_path"])
        modify_initialcondition_xml(last_ts, xmls_dir, model_dict["thermal_output_path"])

    return model_dict, command_dict


def run_model(model_dict, command_dict):

    first = command_dict["parallel_runner"]
    del(command_dict["parallel_runner"])

    second = command_dict["uwbinary"]
    del(command_dict["uwbinary"])

    third = command_dict["input_xmls"]
    del(command_dict["input_xmls"])

    last = command_dict["extra_command_line_flags"]
    del(command_dict["extra_command_line_flags"])

    # Some commmands NEED to come first (mpirun, for example)
    prioritised = " ".join((first, second, third))

    remainder = " ".join(command_dict.values())

    together = " ".join((prioritised, remainder, last))

    command = together.format(**model_dict).split(" ")

    if model_dict["verbose_run"]:
        print "LMR will now run the following command:\n{com}".format(com=together.format(**model_dict))
        sys.stdout.flush()

    try:
        # The sys.stdout is set in main()
        model_run = subprocess.Popen(command, shell=False, stdout=sys.stdout, stderr=subprocess.STDOUT)

        model_run.wait()

        if model_run.returncode != 0:
            error_msg = '\n\nUnderworld did not exit nicely - have a look at its output to try and determine the problem.'
            if model_dict["run_thermal_equilibration_phase"]:
                error_msg += ('\n\nSuggestion - if Underworld failed because of an error similar to:\n'
                              'StGermain/Base/Container/src/ISet.c:205: failed assertion (++self->curSize) <= self->maxSize\n'
                              'it is generally because Underworld is having trouble decomposing the model accross the number\n'
                              'of CPUs you are using. Try either:\n'
                              '  - Using model resolutions that divide nicely (i.e., not prime numbers)\n'
                              '  - Increasing the model resolution\n'
                              '  - Using fewer CPUs')
            raise IOError(error_msg)
    except KeyboardInterrupt:
        model_run.terminate()
        if model_dict["run_thermal_equilibration_phase"]:
            print ('\n=== WARNING ===\nUnderworld thermal equilibration stopped - will interpolate with the '
                   'last timestep to be outputted.')
        else:
            sys.exit("\nYou have cancelled the job - all instances of Underworld have been killed.")
    except OSError as oserr:
        raise OSError(("\n=== ERROR ===\nIssue finding a file. Computer says:\n\t{oserr}\nThe LMR is trying to run this command:\n"
                       "\t {first} {uwbinary} {input_xmls} ...\n\nMake sure all the commands (e.g. {first}) are correct, and all"
                       " the files exist (e.g. {uwbinary}).".format(oserr=oserr, first=first.format(**model_dict), **model_dict)))

def post_model_run(model_dict):
    """
    Clean up thermal equilibration checkpoints if needed.
    """
    if model_dict["run_thermal_equilibration_phase"]:
        last_ts = find_last_timestep(model_dict["thermal_output_path"])
        if model_dict["preserve_thermal_checkpoints"] is False:
            for filename in os.listdir(model_dict["output_path"]):
                if not str(last_ts) in filename and not bool(filename.endswith(("xml", "xdmf", "dat", "txt", "list", "Mesh.linearMesh.00000.h5"))):  # Don't delete files that end with any of these
                    try:
                        os.remove(os.path.join(model_dict["output_path"], filename))
                    except IOError:  # We don't really care much if it can't delete some files
                        pass
                    except OSError:
                        pass


def find_last_timestep(path):
    try:
        # The below line does this:
        #   1) Get the base filename
        #   2) The filename is then split by '.', as the file we're looking for looks like this: VelocityField.00475.h5
        #   3) The second last chunk of the file name (the timestep number) is taken, and converted to int.
        #   4) Get the largest timestep
        last_ts = max( [int(os.path.basename(filename).split(".")[-2]) for filename in glob.glob(os.path.join(path, "VelocityField.*.h5"))] )
    except ValueError:  # You should really catch explicit exceptions...
        if not os.path.isdir(path):
            error_msg = ("\n=== ERROR ===\nThe LMR is looking for folder:\n'{path}'\n"
                    "but it does not exist!\n"
                    "This can happen either when the LMR is looking for an initial-"
                    "condition, or when restarting a model.\n").format(path=path)
        else:
            error_msg = ("\n=== ERROR ===\nUnable to find any files that look like 'VelocityField.*.h5' in the folder:\n'{path}'\n"
                "If you are running a thermo-mechanical model from scratch, this may mean that you\n"
                "need to either run the thermal equilibration phase, or run it for longer.\n"
                "If you are restarting a job, make sure the <description> matches the previous model").format(path=path)
        raise ValueError(error_msg)
    return last_ts


def modify_initialcondition_xml(last_ts, xml_path, initial_condition_path):
    new_temp_file = os.path.join(initial_condition_path, "TemperatureField.{0:05d}.h5".format(last_ts))
    new_mesh_file = os.path.join(initial_condition_path, "Mesh.linearMesh.{0:05d}.h5".format(0)) # UW2.0 will only produce Meshfile 0

    # Python doesn't have a great in-line file editing, so here we use the fileinput function.
    # It redirects the print function to the file itself while in the for loop context.
    # Therefore, we just go through the file line by line, checking if we hit the special text.
    # If so, replace it with the correct text, and print - else, just print.
    triggered_temp = False
    triggered_mesh = False
    try:
        for line in fileinput.input(os.path.join(xml_path, "lmrInitials.xml"), inplace=True):
            if "!!PATH_TO_TEMP_FILE!!" in line:
                triggered_temp = True
                print line.replace("!!PATH_TO_TEMP_FILE!!", new_temp_file),
            elif "!!PATH_TO_MESH_FILE!!" in line:
                triggered_mesh = True
                print line.replace("!!PATH_TO_MESH_FILE!!", new_mesh_file),
            else:
                print line,
    except IOError as err:
        error_msg = ('Problem opening lmrInitials.xml to update the HDF5 initial condition.'
                     'The computer reported:\n\{err}'.format(err = err))
        raise IOError(error_msg)

    if not triggered_temp or not triggered_mesh:
        raise IOError(("ERROR - Problem loading initial conditions.\nThe LMR tries to tell Underworld which initial condition "
                  "files to use by modifying the lmrInitials.xml file - but one of the flags in the file was missing! "
                  "The start of the lmrInitials.xml should look similar to this:\n"
                  "<list name=\"plugins\" mergeType=\"merge\">\n"
                  "    <!-- If you have thermally equilibrated your model, you need to tell Underworld where\n"
                  "         to find the thermal information using the following struct -->\n"
                  "    <struct>\n"
                  "        <param name=\"Type\">Underworld_HDF5ConditionFunction</param>\n"
                  "        <param name=\"FeVariableHDF5Filename\"> !!PATH_TO_TEMP_FILE!! </param>\n"
                  "        <param name=\"MeshHDF5Filename\"> !!PATH_TO_MESH_FILE!! </param>\n"
                  "        <param name=\"TargetFeVariable\"> TemperatureField </param>\n"
                  "        <param name=\"Partitioned\"> False </param>\n"
                  "    </struct>\n"
                  "</list>\n"
                  "If it doesn't, try copying and pasting the above into the lmrInitials.xml, or refer to the LMR bitbucket. "
                  "If you actually want to specify an explicit initial condition, then in lmrStart.xml you need to set the "
                  "<update_xml_information> tag in the <Thermal_Equilibration> section to be false."))


def main():
    # Basic CLI argument parsing - if someone says python lmrRunModel.py <somefilename>,
    # it will send that file through to the XML parser. If no argument is given (or too
    # many), it will just look for lmrStart.xml
    if len(sys.argv) > 1 and len(sys.argv) <= 2:
        raw_dict = load_xml(str(sys.argv[1]))
    else:
        raw_dict = load_xml()

    # STEP 1
    model_dict, command_dict = process_xml(raw_dict)

    # STEP 2
    model_dict, command_dict = prepare_job(model_dict, command_dict)

    if model_dict["write_log_file"]:
        try:
            log_file = open(model_dict["logfile"], "a")
            sys.stdout = log_file
        except IOError as err:
            raise IOErrr("Problem writing to log file {log_file}! Computer says:\n{err}".format(log_file = model_dict["logfile"], err = err))

    # STEP 3
    run_model(model_dict, command_dict)

    # STEP 4
    post_model_run(model_dict)

    if model_dict["write_log_file"]:
        log_file.close()


if __name__ == '__main__':
    main()
