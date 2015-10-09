/**
 * @fileOverview Users landing page JS
 * @requires AngularJS, jQuery
 *
 */

angular.module('UsersPage', ['LandingPage', 'EucaConsoleUtils'])
    .controller('UsersCtrl', function ($scope, $http, eucaHandleError) {
        $scope.userName = '';
        $scope.groupName = '';
        $scope.user_view_url = '';
        $scope.group_view_url = '';
        $scope.user_summary_url = '';
        $scope.disable_url = '';
        $scope.enable_url = '';
        $scope.delete_url = '';
        $scope.getFileEndpoint = '';
        $scope.initPage = function (user_view_url, group_view_url, user_summary_url, disable_url, enable_url, delete_url, getFileEndpoint) {
            $scope.user_view_url = user_view_url;
            $scope.group_view_url = group_view_url;
            $scope.user_summary_url = user_summary_url;
            $scope.disable_url = disable_url;
            $scope.enable_url = enable_url;
            $scope.delete_url = delete_url;
            $scope.getFileEndpoint = getFileEndpoint;
        };
        $scope.revealDelete = function (user) {
            var modal = $('#delete-user-modal');
            $scope.userName = user.user_name;
            modal.foundation('reveal', 'open');
            $('#delete-user-form').attr('action', $scope.delete_url.replace('_name_', user.user_name));
        };
        $scope.revealModalXHR = function (action, user) {
            var modal = $('#' + action + '-user-modal');
            $scope.userName = user.user_name;
            $scope.user = user;
            modal.foundation('reveal', 'open');
        };
        $scope.disableUser = function ($event) {
            $event.preventDefault();
            var url = $scope.disable_url.replace('_name_', $scope.user.user_name);
            var data = "csrf_token="+$('#csrf_token').val();
            $http({method:'POST', url:url, data:data,
                   headers: {'Content-Type': 'application/x-www-form-urlencoded'}}).
              success(function(oData) {
                var results = oData ? oData.results : [];
                // could put data back into form, but form already contains changes
                if (oData.error === undefined) {
                    Notify.success(oData.message);
                    $scope.updateUser();
                } else {
                    Notify.failure(oData.message);
                }
              }).
              error(function (oData, status) {
                eucaHandleError(oData, status);
              });
            $('#disable-user-modal').foundation('reveal', 'close');
        };
        $scope.updateUser = function () {
            var url = $scope.user_summary_url.replace('_name_', $scope.user.user_name);
            $http.get(url).success(function(oData) {
                var results = oData ? oData.results : [];
                // add these values to the item record so that angular will see them
                $scope.user.has_password = results.has_password;
                $scope.user.num_keys = results.num_keys;
                $scope.user.user_enabled = results.user_enabled;
            });
        };
        $scope.enableUser = function ($event) {
            $event.preventDefault();
            var generate = $event.target.random_password.checked;
            var url = $scope.enable_url.replace('_name_', $scope.user.user_name);
            var csrf_token = $('#csrf_token').val();
            var data = '';
            if (generate === true) { // handle file return
                data = "random_password=y&csrf_token="+csrf_token;
                $http({method:'POST', url:url, data:data,
                       headers: {'Content-Type': 'application/x-www-form-urlencoded'}}).
                  success(function(oData) {
                    var results = oData ? oData.results : [];
                    Notify.success(oData.message);
                    $scope.updateUser();
                    $.generateFile({
                        csrf_token: csrf_token,
                        filename: 'not-used', // let the server set this
                        content: 'none',
                        script: $scope.getFileEndpoint
                    });
                }).error(function (oData, status) {
                    eucaHandleError(oData, status);
                });
            } else { // deal with normal REST call
                data = "csrf_token="+csrf_token;
                $http({method:'POST', url:url, data:data,
                       headers: {'Content-Type': 'application/x-www-form-urlencoded'}}).
                  success(function(oData) {
                    var results = oData ? oData.results : [];
                    if (oData.error === undefined) {
                        Notify.success(oData.message);
                        $scope.updateUser();
                    } else {
                        Notify.failure(oData.message);
                    }
                  }).
                  error(function (oData, status) {
                    var errorMsg = oData.message || '';
                    Notify.failure(errorMsg);
                  });
            }
            $('#enable-user-modal').foundation('reveal', 'close');
        };
        $scope.linkUser = function (user, fragment) {
            window.location = $scope.user_view_url.replace('_name_', user.user_name)+fragment;
        };
        $scope.$on('itemsLoaded', function($event, items) {
            for (var i=0; i < items.length; i++) {
                var url = $scope.user_summary_url.replace('_name_', items[i].user_name);
                $scope.addUserSummaryData(items, url);
            }
        });
        $scope.addUserSummaryData = function(items, url) {
            var theItems = items;
            $http.get(url).success(function(oData) {
                var results = oData ? oData.results : [];
                // search item list for this user
                for (var k=0; k<theItems.length; k++) {
                    if (theItems[k].user_name == results.user_name) {
                        // add these values to the item record so that angular will see them
                        theItems[k].has_password = results.has_password;
                        theItems[k].num_keys = results.num_keys;
                        theItems[k].user_enabled = results.user_enabled;
                        break;
                    }
                }
            }).error(function (oData, status) {
                // ignore
            });
        };
    })
;
