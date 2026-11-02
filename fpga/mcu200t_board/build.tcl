# ============================================================
# MCU200T board-level project build script
# E203 RISC-V SoC + Dilithium PQC accelerator
# Target: xc7a200tfbg484-2, Vivado 2019.2
# ============================================================

set proj_name "mcu200t_board"
set proj_dir  "D:/FPGA/my_fpga/mcu200t_board"
set part      "xc7a200tfbg484-2"
set rtl_root  "D:/FPGA/e203_hbirdv2-master/rtl/e203"
set fpga_dir  "D:/FPGA/e203_hbirdv2-master/fpga/ddr200t"

create_project $proj_name $proj_dir -part $part -force
set_property target_language Verilog [current_project]

# ---------------- Verilog sources (recursive) ----------------
set vfiles [concat \
  [glob -nocomplain $rtl_root/*.v] \
  [glob -nocomplain $rtl_root/*/*.v] \
  [glob -nocomplain $rtl_root/*/*/*.v]]
puts "INFO: adding [llength $vfiles] verilog files"
add_files -norecurse $vfiles

# ---------------- VHDL sources (dilithium keccak etc.) ----------------
set vhdfiles [glob -nocomplain $rtl_root/*/*.vhd]
puts "INFO: adding [llength $vhdfiles] vhdl files"
add_files -norecurse $vhdfiles

# ---------------- include dirs ----------------
set_property include_dirs [list \
  $rtl_root/core \
  $rtl_root/perips/apb_i2c] [get_filesets sources_1]

# ---------------- top module ----------------
add_files -norecurse $fpga_dir/src/system.v
set_property top system [current_fileset]

# ---------------- constraints ----------------
add_files -fileset constrs_1 -norecurse $fpga_dir/constrs/nuclei-master.xdc
add_files -fileset constrs_1 -norecurse $fpga_dir/constrs/nuclei-config.xdc

# ---------------- IP cores ----------------
set ipdir $proj_dir/ip
file mkdir $ipdir

create_ip -vendor xilinx.com -library ip -name clk_wiz -module_name mmcm -dir $ipdir -force
set_property -dict [list \
  CONFIG.PRIMITIVE {MMCM} \
  CONFIG.RESET_TYPE {ACTIVE_LOW} \
  CONFIG.CLKOUT1_USED {true} \
  CONFIG.CLKOUT2_USED {true} \
  CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {8.388} \
  CONFIG.CLKOUT2_REQUESTED_OUT_FREQ {16.000} \
  ] [get_ips mmcm]

create_ip -vendor xilinx.com -library ip -name proc_sys_reset -module_name reset_sys -dir $ipdir -force
set_property -dict [list \
  CONFIG.C_EXT_RESET_HIGH {false} \
  CONFIG.C_AUX_RESET_HIGH {false} \
  CONFIG.C_NUM_BUS_RST {1} \
  CONFIG.C_NUM_PERP_RST {1} \
  CONFIG.C_NUM_INTERCONNECT_ARESETN {1} \
  CONFIG.C_NUM_PERP_ARESETN {1} \
  ] [get_ips reset_sys]

generate_target all [get_files $ipdir/mmcm/mmcm.xci]
generate_target all [get_files $ipdir/reset_sys/reset_sys.xci]

# IP out-of-context synthesis runs
create_ip_run [get_files -of_objects [get_fileset sources_1] $ipdir/mmcm/mmcm.xci]
create_ip_run [get_files -of_objects [get_fileset sources_1] $ipdir/reset_sys/reset_sys.xci]

launch_runs mmcm_synth_1 reset_sys_synth_1 -jobs 8
wait_on_run mmcm_synth_1
wait_on_run reset_sys_synth_1
puts "INFO: mmcm_synth_1      progress = [get_property PROGRESS [get_runs mmcm_synth_1]] status = [get_property STATUS [get_runs mmcm_synth_1]]"
puts "INFO: reset_sys_synth_1 progress = [get_property PROGRESS [get_runs reset_sys_synth_1]] status = [get_property STATUS [get_runs reset_sys_synth_1]]"

# ---------------- synthesis ----------------
launch_runs synth_1 -jobs 8
wait_on_run synth_1
set synth_prog [get_property PROGRESS [get_runs synth_1]]
set synth_stat [get_property STATUS [get_runs synth_1]]
puts "INFO: synth_1 progress = $synth_prog status = $synth_stat"
if {$synth_prog != "100%"} {
  puts "ERROR: synthesis failed, aborting"
  exit 1
}

open_run synth_1 -name synth_1
report_utilization -file $proj_dir/utilization_synth.rpt
report_timing_summary -file $proj_dir/timing_synth.rpt

# ---------------- implementation (to bitstream) ----------------
launch_runs impl_1 -to_step write_bitstream -jobs 8
wait_on_run impl_1
set impl_prog [get_property PROGRESS [get_runs impl_1]]
set impl_stat [get_property STATUS [get_runs impl_1]]
puts "INFO: impl_1 progress = $impl_prog status = $impl_stat"
if {$impl_prog != "100%"} {
  puts "ERROR: implementation failed"
  exit 1
}

open_run impl_1 -name impl_1
report_utilization -file $proj_dir/utilization_impl.rpt
report_timing_summary -file $proj_dir/timing_impl.rpt
report_drc -file $proj_dir/drc_impl.rpt

puts "INFO: BUILD DONE"
exit 0
