
module.exports = function(grunt) {

  // Project configuration.
  grunt.initConfig({
      pkg: grunt.file.readJSON('package.json'),
      bowercopy: {
          options: {
              // Bower components folder will be removed afterwards
              clean: true
          },
          angular: {
              options: {
                  destPrefix: 'eucaconsole/static/js/thirdparty/angular'
              },
              files: {
                'angular.js': 'angular/angular.js',
                'angular.min.js': 'angular/angular.min.js',
                'angular-sanitize.min.js': 'angular-sanitize/angular-sanitize.min.js',
                'angular-mocks.js': 'angular-mocks/angular-mocks.js',
              }
          },
          jquery: {
              options: {
                  destPrefix: 'eucaconsole/static/js/thirdparty/jquery'
              },
              files: {
                'jquery.min.js': 'jquery/dist/jquery.min.js'
              }
          },
          jasmine: {
              options: {
                  destPrefix: 'eucaconsole/static/js/thirdparty/jasmine'
              },
              files: {
                'jasmine_favicon.png': 'jasmine/images/jasmine_favicon.png',
                'jasmine.css': 'jasmine/lib/jasmine-core/jasmine.css',
                'jasmine.js': 'jasmine/lib/jasmine-core/jasmine.js',
                'jasmine-html.js': 'jasmine/lib/jasmine-core/jasmine-html.js',
                'console.js': 'jasmine/lib/console/console.js',
                'boot.js': 'jasmine/lib/jasmine-core/boot/boot.js'
              }
          },
          jasmine_jquery: {
              options: {
                  destPrefix: 'eucaconsole/static/js/thirdparty/jasmine'
              },
              files: {
                'jasmine-jquery.js': 'jasmine-jquery/lib/jasmine-jquery.js'
              }
          },
          font_awesome: {
              files: {
                'eucaconsole/static/fonts/font-awesome': 'components-font-awesome/fonts/*',
                'eucaconsole/static/css/thirdparty': 'components-font-awesome/css/*.css',
                'eucaconsole/static/sass/font-awesome':'components-font-awesome/scss/*.scss'
              }
          },
          foundation: {
              files: {
                  'eucaconsole/static/js/thirdparty/foundation': 'foundation/js/**/foundation*.js',
                  'eucaconsole/static/sass/foundation': 'foundation/scss/foundation'
              }
          },
          foundation_datepicker: {
              files: {
                'eucaconsole/static/js/thirdparty/foundation-datepicker': 'foundation-datepicker/js/foundation-datepicker*.js',
                'eucaconsole/static/sass': 'foundation-datepicker/css/foundation-datepicker.scss',
              }
          },
          angular_magic_search: {
              options: {
              },
              files: {
                'eucaconsole/static/js/thirdparty/magic-search': 'angular-magic-search/magic_search.*'
              }
          },
          angular_smart_table: {
              options: {
                  destPrefix: 'eucaconsole/static/js/thirdparty/angular'
              },
              files: {
                'angular-smart-table.js': 'angular-smart-table/dist/smart-table.js',
                'angular-smart-table.min.js': 'angular-smart-table/dist/smart-table.min.js'
              }
          },
          d3: {
              options: {
                  destPrefix: 'eucaconsole/static/js/thirdparty/d3'
              },
              files: {
                  'd3.js': 'd3/d3.js',
                  'd3.min.js': 'd3/d3.min.js',
                  'LICENSE.txt': 'd3/LICENSE'
              }
          },
          nvd3: {
              options: {
                  destPrefix: 'eucaconsole/static/js/thirdparty/nvd3'
              },
              files: {
                  'nv.d3.js': 'nvd3/build/nv.d3.js',
                  'nv.d3.min.js': 'nvd3/build/nv.d3.min.js',
                  'nv.d3.css': 'nvd3/build/nv.d3.css',
                  'nv.d3.min.css': 'nvd3/build/nv.d3.min.css'
              }
          },
          angular_chosen: {
              options: {
              },
              files: {
                'eucaconsole/static/js/thirdparty/angular': 'angular-chosen-localytics/chosen.*'
              }
          },
          sticky_table_headers: {
              options: {
                  destPrefix: 'eucaconsole/static/js/thirdparty/jquery'
              },
              files: {
                'jquery.stickytableheaders.js': 'StickyTableHeaders/js/jquery.stickytableheaders.js',
                'jquery.stickytableheaders.min.js': 'StickyTableHeaders/js/jquery.stickytableheaders.min.js'
              }
          },
          angular_filters: {
              options: {
                  destPrefix: 'eucaconsole/static/js/thirdparty/angular'
              },
              files: {
                'angular-filter.js': 'angular-filter/dist/angular-filter.js',
                'angular-filter.min.js': 'angular-filter/dist/angular-filter.min.js'
              }
          }
      },
      jshint: {
          options: {
              reporter: require('jshint-stylish')
          },
          all: ['Gruntfile.js',
                'eucaconsole/static/js/pages/*.js',
                'eucaconsole/static/js/widgets/*.js',
                'eucaconsole/static/js/jasmine-spec/*.js']
      },
      karma: {
          unit: {
              configFile: 'karma.conf.js'
          },
          ci: {
              configFile: 'karma.conf.js',
              singleRun: true
          }
      },
      clean: {
          backup: ["eucaconsole.backup"],
          minified: ["eucaconsole/static/js/minified"]
      },
      copy: {
          restore: {
              files: [{ 
                  expand: true,
                  cwd: 'eucaconsole.backup/eucaconsole/',
                  src: ['**/*'],
                  dest: 'eucaconsole'
              }],
              options: {
                  force: true,
                  mode: true,
                  timestamp: true
              }
          },
          backup: {
              files: [{ 
                  expand: true,
                  src: ['eucaconsole/**'],
                  dest: 'eucaconsole.backup/'
              }],
              options: {
                  force: false,
                  mode: true,
                  timestamp: true
              }
          }
      },
      htmlmin: { 
          production: {
              options: {
                  removeComments: true,
                  collapseWhitespace: true,
                  conservativeCollapse: true
              },
              files: [{
                  expand: true,
                  cwd: 'eucaconsole/templates',
                  src: '**/*.pt',
                  dest: 'eucaconsole/templates'
              }]
          }
      },
      replace: {
          min: {
              expand: true,
              src: 'eucaconsole/templates/**/*.pt',
              overwrite: true,
              replacements: [{
                  from: /static\/js\/pages\/(.+)\.js/g,
                  to: 'static/js/minified/pages/$1.min.js'
              }, {
                  from: /static\/js\/widgets\/(.+)\.js/g,
                  to: 'static/js/minified/widgets/$1.min.js' 
              }]             
          },
          nomin: {
              expand: true,
              src: 'eucaconsole/templates/**/*.pt',
              overwrite: true,
              replacements: [{
                  from: /static\/js\/minified\/pages\/(.+)\.min\.js/g,
                  to: 'static/js/pages/$1.js' 
              }, {
                  from: /static\/js\/minified\/widgets\/(.+)\.min\.js/g,
                  to: 'static/js/widgets/$1.js' 
              }]
          }
      },
      uglify: {
          minify: {
              options: {
                  mangle: false,
                  compress: {
                      drop_console: true
                  }
              },
              files: [
                  {
                      expand: true,     // Enable dynamic expansion.
                      cwd: 'eucaconsole/static/js/',      // Src matches are relative to this path.
                      src: ['pages/*.js', 'widgets/*.js'], // Actual pattern(s) to match.
                      dest: 'eucaconsole/static/js/minified/',   // Destination path prefix.
                      ext: '.min.js',   // Dest filepaths will have this extension.
                      extDot: 'first'   // Extensions in filenames begin after the first dot
                  }
              ]
          }
      },
      compass: {
          sass: {
              options: {
                  outputStyle: 'compact',
                  noLineComments: '',
                  sassDir: 'eucaconsole/static/sass',
                  cssDir: 'eucaconsole/static/css'
              }
          }
      },
      watch: {
          scripts: {
              files: ['eucaconsole/static/js/**/*.js'],
              tasks: ['karma:ci', 'jshint'],
              options: {
                  spawn: false
              }
          },
          sass: {
              files: ['eucaconsole/static/sass/**/*.scss'],
              tasks: ['compass'],
              options: {
                  spawn: false
              }
          }
      },
      htmllint: {
          options: {
              ignore: [
                  /Attribute “ng-[a-z-]+” not allowed/,
                  /Attribute “tal:[a-z-]+” not allowed/,
                  /Attribute “tal:[a-z-]+” is not serializable/,
                  /Attribute “i18n:[a-z-]+” not allowed/,
                  /Attribute “i18n:[a-z-]+” is not serializable/,
                  /Attribute “metal:[a-z-]+” is not serializable/,
              ] 
          },
          all: ['eucaconsole/static/html/**/*.html', 'eucaconsole/templates/**/*.pt'],
          templates: ['eucaconsole/templates/**/*.pt'],
          dialogs: ['eucaconsole/templates/dialogs/*.pt'],
          directives: ['eucaconsole/static/html/directives/*.html'],
          help: ['eucaconsole/static/html/help/*.html'],
          elb: ['eucaconsole/templates/dialogs/select_certificate_dialog.pt',
                'eucaconsole/templates/panels/elb_listener_editor.pt',
                'eucaconsole/static/html/directives/instance_selector.html',
                'eucaconsole/templates/elbs/elb_wizard.pt'],
      }
  });

  // Load the plugins
  grunt.loadNpmTasks('grunt-contrib-clean');
  grunt.loadNpmTasks('grunt-contrib-copy');
  grunt.loadNpmTasks('grunt-contrib-jshint');
  grunt.loadNpmTasks('grunt-contrib-htmlmin');
  grunt.loadNpmTasks('grunt-contrib-uglify');
  grunt.loadNpmTasks('grunt-contrib-watch');
  grunt.loadNpmTasks('grunt-bowercopy');
  grunt.loadNpmTasks('grunt-karma');
  grunt.loadNpmTasks('grunt-text-replace');
  grunt.loadNpmTasks('grunt-contrib-compass');
  grunt.loadNpmTasks('grunt-html');

  // Default task(s).
  grunt.registerTask('default', ['watch']);
  grunt.registerTask('runtest', ['karma:ci', 'jshint']);
  grunt.registerTask('commitcheck', ['runtest']);
  grunt.registerTask('production', ['copy:backup', 'uglify', 'replace:min', 'htmlmin']);
  grunt.registerTask('restore', ['copy:restore', 'clean']);

};
