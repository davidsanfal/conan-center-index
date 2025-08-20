from conan import ConanFile
from conan.tools.env import Environment
from conan.tools.microsoft import VCVars, is_msvc, msvc_runtime_flag
from conan.tools.meson import Meson, MesonToolchain
from conan.tools.gnu import PkgConfigDeps
from conan.tools.layout import basic_layout
from conan.tools.files import rm, rmdir, chdir, patch, get, copy
from conan.tools.scm import Version
from conan.errors import ConanInvalidConfiguration
import glob
import os
import shutil


class GStPluginsBadConan(ConanFile):
    name = "gst-plugins-bad"
    description = "GStreamer is a development framework for creating applications like media players, video editors, " \
                  "streaming media broadcasters and so on"
    topics = ("gstreamer", "multimedia", "video", "audio", "broadcasting", "framework", "media")
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://gstreamer.freedesktop.org/"
    license = "GPL-2.0-only"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "with_introspection": [True, False],
        }
    default_options = {
        "shared": False,
        "fPIC": True,
        "with_introspection": False,
        }
    exports_sources = ["patches/*.patch"]

    def validate(self):
        if self.options.shared != self.dependencies["gstreamer"].options.shared or self.options.shared != self.dependencies["glib"].options.shared or self.options.shared != self.dependencies["gst-plugins-base"].options.shared:
            # https://gitlab.freedesktop.org/gstreamer/gst-build/-/issues/133
            raise ConanInvalidConfiguration("GLib, GStreamer and GstPlugins must be either all shared, or all static")
        if Version(self.version) >= "1.18.2" and\
           self.settings.compiler == "gcc" and\
           Version(self.settings.compiler.version) < "5":
            raise ConanInvalidConfiguration(
                "gst-plugins-good %s does not support gcc older than 5" % self.version
            )
        if self.options.shared and str(msvc_runtime_flag(self)).startswith("MT"):
            raise ConanInvalidConfiguration('shared build with static runtime is not supported due to the FlsAlloc limit')

    def configure(self):
        if self.options.shared:
            del self.options.fPIC
        del self.settings.compiler.libcxx
        del self.settings.compiler.cppstd
        self.options['gstreamer'].shared = self.options.shared
        self.options['gst-plugins-base'].shared = self.options.shared

    def config_options(self):
        if self.settings.os == 'Windows':
            del self.options.fPIC

    def requirements(self):
        self.requires("glib/2.78.3")
        self.requires("gstreamer/1.19.2")
        self.requires("gst-plugins-base/1.19.1")

    def build_requirements(self):
        self.tool_requires("meson/[>=1.2 <2]")
        if not shutil.which("pkg-config"):
            self.build_requires("pkgconf/1.7.4")
        if self.settings.os == 'Windows':
            self.build_requires("winflexbison/2.5.24")
        else:
            self.build_requires("bison/3.7.6")
            self.build_requires("flex/2.6.4")
        if self.options.with_introspection:
            self.build_requires("gobject-introspection/1.68.0")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def layout(self):
        basic_layout(self, src_folder="src")

    def generate(self):
        tc = MesonToolchain(self)

        if is_msvc(self):
            env = Environment()
            env.append(VCVars(self).vars)
            envvars = env.vars(self, scope="build")
            envvars.save_script("vc_vars")
            tc.project_options["c_link_args"] = "-lws2_32"
            tc.project_options["cpp_link_args"] = "-lws2_32"
            tc.project_options["c_args"] = "-%s" % self.settings.compiler.runtime
            tc.project_options["cpp_args"] = "-%s" % self.settings.compiler.runtime
            if int(str(self.settings.compiler.version)) < 14:
                tc.project_options["c_args"] = tc.project_options["c_args"] + " -Dsnprintf=_snprintf"
                tc.project_options["cpp_args"] = tc.project_options["cpp_args"] + " -Dsnprintf=_snprintf"

        if self.settings.get_safe("compiler.runtime"):
            tc.project_options["b_vscrt"] = str(self.settings.compiler.runtime).lower()

        tc.project_options["tools"] = "disabled"
        tc.project_options["examples"] = "disabled"
        tc.project_options["benchmarks"] = "disabled"
        tc.project_options["tests"] = "disabled"
        tc.project_options["wrap_mode"] = "nofallback"
        tc.project_options["introspection"] = "enabled" if self.options.with_introspection else "disabled"
        tc.generate()
        deps = PkgConfigDeps(self)
        deps.generate()

    def build(self):
        for patchfile in self.conan_data.get("patches", {}).get(self.version, []):
            patch(self, **patchfile)
        meson = Meson(self)
        meson.configure()
        meson.build()

    def _fix_library_names(self, path):
        # regression in 1.16
        if is_msvc(self):
            with chdir(path):
                for filename_old in glob.glob("*.a"):
                    filename_new = filename_old[3:-2] + ".lib"
                    self.output.info("rename %s into %s" % (filename_old, filename_new))
                    shutil.move(filename_old, filename_new)

    def package(self):
        copy(self, "COPYING", self.source_folder, os.path.join(self.package_folder, "licenses"))
        meson = Meson(self)
        meson.install()

        self._fix_library_names(os.path.join(self.package_folder, "lib"))
        self._fix_library_names(os.path.join(self.package_folder, "lib", "gstreamer-1.0"))
        rmdir(self, os.path.join(self.package_folder, "share"))
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))
        rmdir(self, os.path.join(self.package_folder, "lib", "gstreamer-1.0", "pkgconfig"))
        rm(self, "*.pdb", self.package_folder)

    def package_info(self):

        plugins = ["accurip",
                   "adpcmdec",
                   "adpcmenc",
                   "aiff",
                   "asfmux",
                   "audiobuffersplit",
                   "audiofxbad",
                   "audiolatency",
                   "audiomixmatrix",
                   "audiovisualizers",
                   "autoconvert",
                   "bayer",
                   "camerabin",
                   "codecalpha",
                   "coloreffects",
                   "debugutilsbad",
                   "dvbsubenc",
                   "dvbsuboverlay",
                   "dvdspu",
                   "faceoverlay",
                   "festival",
                   "fieldanalysis",
                   "freeverb",
                   "frei0r",
                   "gaudieffects",
                   "gdp",
                   "geometrictransform",
                   "id3tag",
                   "inter",
                   "interlace",
                   "ivfparse",
                   "ivtc",
                   "jp2kdecimator",
                   "jpegformat",
                   "rfbsrc",
                   "midi",
                   "mpegpsdemux",
                   "mpegpsmux",
                   "mpegtsdemux",
                   "mpegtsmux",
                   "mxf",
                   "netsim",
                   "rtponvif",
                   "pcapparse",
                   "pnm",
                   "proxy",
                   "legacyrawparse",
                   "removesilence",
                   "rist",
                   "rtmp2",
                   "rtpmanagerbad",
                   "sdpelem",
                   "segmentclip",
                   "siren",
                   "smooth",
                   "speed",
                   "subenc",
                   "switchbin",
                   "timecode",
                   "transcode",
                   "videofiltersbad",
                   "videoframe_audiolevel",
                   "videoparsersbad",
                   "videosignal",
                   "vmnc",
                   "y4mdec"]

        gst_plugin_path = os.path.join(self.package_folder, "lib", "gstreamer-1.0")
        if self.options.shared:
            self.output.info("Appending GST_PLUGIN_PATH env var : %s" % gst_plugin_path)
            self.cpp_info.bindirs.append(gst_plugin_path)
            self.runenv_info.prepend_path("GST_PLUGIN_PATH", gst_plugin_path)
            self.env_info.GST_PLUGIN_PATH.append(gst_plugin_path)
        else:
            self.cpp_info.defines.append("GST_PLUGINS_BAD_STATIC")
            self.cpp_info.libdirs.append(gst_plugin_path)
            self.cpp_info.libs.extend(["gst%s" % plugin for plugin in plugins])

        self.cpp_info.includedirs = []
        # self.cpp_info.includedirs = ["include", os.path.join("include", "gstreamer-1.0")]
