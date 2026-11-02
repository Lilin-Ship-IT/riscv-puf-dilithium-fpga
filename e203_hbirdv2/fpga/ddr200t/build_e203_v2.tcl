# ============================================================
# E203 (DDR200T) 一键构建脚本 —— Vivado batch 模式 (v2 稳定版)
# 用法: 在 cmd 中 cd 到 fpga/ddr200t 目录后执行:
#   D:\Xilinx\Vivado\2019.2\bin\vivado.bat -mode batch -source build_e203.tcl
# v2: 限制并行线程为4，降低子进程被杀毒/内存问题误杀的概率
# ============================================================

set_param general.maxThreads 4

set base {D:/FPGA/e203_hbirdv2-master/fpga}

# ---------- 第0步: install（幂等，重复跑安全） ----------
file mkdir $base/install
file delete -force $base/install/rtl
file copy D:/FPGA/e203_hbirdv2-master/rtl/e203 $base/install/rtl
file copy -force $base/ddr200t/src/system.v $base/install/rtl/system.v
set f [file join $base install rtl core e203_defines.v]
set fd [open $f r]; set c [read $fd]; close $fd
if {![string match {`define FPGA_SOURCE*} $c]} {
  set fd [open $f w]
  puts $fd "`define FPGA_SOURCE"
  puts -nonewline $fd $c
  close $fd
}
puts "===== install done ====="

# ---------- 进入板级目录 ----------
cd $base/ddr200t

# ---------- 环境变量（VSRCS；故意不设 EXTRA_VSRCS，绕开 GUI 空串 bug） ----------
set v1 [glob $base/install/rtl/*.v]
set v1 [concat $v1 [glob $base/install/rtl/*/*.v]]
set v1 [concat $v1 [glob $base/install/rtl/*/*/*.v]]
set ::env(VSRCS) [join $v1 " "]

# ---------- bram.tcl 桩（上游仓库缺这个文件） ----------
set fh [open script/bram.tcl w]
puts $fh "proc write_mmi {fname inst} {puts \"STUB write_mmi: \$fname \$inst\"}"
close $fh

# ---------- 构建 ----------
source script/board.tcl
source script/prologue.tcl
source script/init.tcl
source script/impl.tcl

# ---------- 生成 mcs ----------
write_cfgmem -format mcs -interface spix4 -size 16 -loadbit {up 0x000000 obj/system.bit} -file obj/system.mcs -force

puts "===== BUILD ALL DONE ====="
