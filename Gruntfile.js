
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
                'angular.min.js': 'angular/angular.min.js',
                'angular-sanitize.min.js': 'angular-sanitize/angular-sanitize.min.js',
                'angular-mocks.js': 'angular-mocks/angular-mocks.js'
              }
          },
          jquery: {
              options: {
                  destPrefix: 'eucaconsole/static/js/thirdparty/jquery'
              },
              files: {
                'jquery.min.js': 'jquery/jquery.min.js'
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
          angular_magic_search: {
              options: {
              },
              files: {
                'eucaconsole/static/js/thirdparty/magic-search': 'angular-magic-search/magic_search.*'
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
                'eucaconsole/static/js/jasmine/spec/*.js']
      },
      karma: {
          unit: {
              configFile: 'karma.conf.js'
          },
          ci: {
              configFile: 'karma.conf.js',
              singleRun: true,
          }
      }
  });

  // Load the plugins
  grunt.loadNpmTasks('grunt-contrib-jshint');
  grunt.loadNpmTasks('grunt-bowercopy');
  grunt.loadNpmTasks('grunt-karma');

  // Default task(s).
  grunt.registerTask('default', ['jshint']);

};
