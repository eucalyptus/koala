/**
 * @fileOverview Buckets landing page JS
 * @requires AngularJS, jQuery
 *
 */

angular.module('BucketsPage', ['LandingPage', 'EucaConsoleUtils'])
    .controller('BucketsCtrl', function ($scope, $http, $timeout, eucaUnescapeJson, eucaFixHiddenTooltips) {
        $http.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';
        $scope.bucketName = '';
        $scope.updateVersioningAction = '';
        $scope.bucketCounts = {};
        $scope.versionCounts = {};
        $scope.bucketVersioningStatus = {};
        $scope.bucketVersioningAction = {};
        $scope.countsLoading = {};
        $scope.versioningStatusLoading = {};
        $scope.prefix = '';
        $scope.folder = '';  // gets set if we are copying a folder specifically
        $scope.copyingAll = false;
        $scope.progress = 0;
        $scope.total = 0;
        $scope.chunkSize = 10;  // set this based on how many keys we want to copy at once
        $scope.index = 0;
        $scope.items = null;
        $scope.hasCopyItem = false;
        $scope.hasCopyFolder = false;
        $scope.fetchingUrl = false;
        $scope.initController = function (optionsJson) {
            var options = JSON.parse(eucaUnescapeJson(optionsJson));
            $scope.bucketObjectsCountUrl = options.bucket_objects_count_url;
            $scope.updateVersioningFormUrl = options.update_versioning_url;
            $scope.copyObjUrl = options.copy_object_url;
            $scope.getKeysGenericUrl = options.get_keys_generic_url;
            $scope.putKeysUrl = options.put_keys_url;
            $scope.uploadUrl = options.upload_url;
            $scope.contentsUrl = options.contents_url;
            $scope.itemUrl = options.bucket_item_url;
            $scope.storageKey = options.storage_key + "shared_buckets";
            $scope.updatePasteValues();
            eucaFixHiddenTooltips();
        };
        $scope.revealModal = function (action, bucket) {
            var modal = $('#' + action + '-modal');
            $scope.bucketName = bucket.bucket_name;
            $scope.bucketCount = $scope.bucketCounts[$scope.bucketName];
            $scope.versionCount = $scope.versionCounts[$scope.bucketName];
            // Set form action based on bucket choice
            var form_action = $('#' + action + '-form').attr('action');
            form_action = form_action.replace('_name_', $scope.bucketName);
            $('#' + action + '-form').attr('action', form_action);
            modal.foundation('reveal', 'open');
        };
        $scope.revealVersioningModal = function (versioningAction, bucket) {
            // Need distinct handling of the versioning modal since bucket versioning info is lazy-loaded
            var modal = $('#update-versioning-modal');
            var versioningForm = $('#update-versioning-form');
            var form_action = versioningForm.attr('action');
            $scope.updateVersioningAction = versioningAction;
            $scope.bucketName = bucket.bucket_name;
            $scope.bucketCount = $scope.bucketCounts[$scope.bucketName];
            // Set form action based on bucket choice
            form_action = form_action.replace('_name_', $scope.bucketName);
            versioningForm.attr('action', form_action);
            modal.foundation('reveal', 'open');
        };
        $scope.getVersioningActionFromStatus = function (versioningStatus) {
            if (versioningStatus == 'Disabled' || versioningStatus == 'Suspended') {
                return 'enable';
            }
            return 'disable';
        };
        $scope.$on('itemsLoaded', function($event, items) {
            angular.forEach(items, function(item, key) {
                var bucketName = item.bucket_name;
                var objectsCountUrl = $scope.bucketObjectsCountUrl.replace('_name_', bucketName);
                $scope.countsLoading[bucketName] = true;
                $scope.versioningStatusLoading[bucketName] = true;
                $http.get(objectsCountUrl).success(function(oData) {
                    var results = oData ? oData.results : {},
                        versioningStatus = results.versioning_status;
                    $scope.bucketCounts[bucketName] = results.object_count;
                    $scope.versionCounts[bucketName] = results.version_count;
                    $scope.bucketVersioningStatus[bucketName] = versioningStatus;
                    $scope.bucketVersioningAction[bucketName] = $scope.getVersioningActionFromStatus(versioningStatus);
                    $scope.countsLoading[bucketName] = false;
                    $scope.versioningStatusLoading[bucketName] = false;
                }).error(function (oData, status) {
                    var errorMsg = oData.message || null;
                    if (errorMsg) {
                        if (status === 403 || status === 400) {
                            $('#timed-out-modal').foundation('reveal', 'open');
                        } else {
                            Notify.failure(errorMsg);
                        }
                    }
                });
            });
            if (Modernizr.localstorage) {
                var saved_names = localStorage.getItem($scope.storageKey);
                if (saved_names) {
                    angular.forEach(saved_names.split(','), function(item, key) {
                        items.push({'bucket_name': item, 'creation_date': 'unknown',
                            'shared': true, 'contents_url': $scope.contentsUrl.replace('_name_', item)});
                    });
                }
            }
        });
        $scope.updatePasteValues = function() {
            $scope.pasteBuffer = Modernizr.sessionstorage && sessionStorage.getItem('copy-object-buffer');
            $scope.hasCopyItem = false;
            $scope.hasCopyFolder = false;
            if ($scope.pasteBuffer !== null) {
                $scope.pasteBucket = $scope.pasteBuffer.slice(0, $scope.pasteBuffer.indexOf('/'));
                $scope.pasteKey = $scope.pasteBuffer.slice($scope.pasteBuffer.indexOf('/')+1);
                $scope.pastePath = $scope.pasteKey.slice(0, $scope.pasteKey.slice(0, $scope.pasteKey.length-1).lastIndexOf('/')+1);
                // initially, set based on key ending
                if ($scope.pasteBuffer.indexOf('/', $scope.pasteBuffer.length - 1) !== -1) {
                    $scope.hasCopyFolder = true;
                }
                else {
                    $scope.hasCopyItem = true;
                }
            }
        };
        $scope.bucketCanCopyItem = function (item) {
            if (item && $scope.pasteBucket == item.bucket_name && $scope.pastePath === '') {
                return false;
            }
            return $scope.hasCopyItem;
        };
        $scope.bucketCanCopyFolder = function (item) {
            if (item && $scope.pasteBucket == item.bucket_name && $scope.pastePath === '') {
                return false;
            }
            return $scope.hasCopyFolder;
        };
        $scope.doPaste = function (bucket) {
            var id = $('.open').attr('id');  // hack to close action menu
            $('#table-'+id).trigger('click');
            $scope.bucketName = bucket.bucket_name;
            var path = Modernizr.sessionstorage && sessionStorage.getItem('copy-object-buffer');
            if (path.indexOf('/', path.length - 1) !== -1) {
                // this is a folder, so send it off to the folder handling code
                $scope.startFolderCopy(path);
                return;
            }
            bucket = path.slice(0, path.indexOf('/'));
            var key = path.slice(path.indexOf('/') + 1);
            var dst_key = path.slice(path.lastIndexOf('/') + 1);
            var url = $scope.copyObjUrl.replace('_name_', $scope.bucketName).replace('_subpath_', '');
            var data = "csrf_token=" + $('#csrf_token').val() + '&src_bucket=' + bucket + '&src_key=' + key;
            $http({method:'POST', url:url, data:data,
                   headers: {'Content-Type': 'application/x-www-form-urlencoded'}}).
              success(function(oData) {
                var results = oData ? oData.results : [];
                if (oData.error === undefined) {
                    $scope.$broadcast('refresh');
                } else {
                    Notify.failure(oData.message);
                }
              }).
              error(function (oData, status) {
                var errorMsg = oData.message || '';
                Notify.failure(errorMsg);
              });
        };
        $scope.startFolderCopy = function (path) {
            $scope.src_bucket = path.slice(0, path.indexOf('/'));
            $scope.src_path = path.slice(path.indexOf('/')+1);
            var url = $scope.getKeysGenericUrl;
            url = url.replace('_name_', $scope.src_bucket);
            url = url.replace('_subpath_', $scope.src_path);
            // slice and dice to get portion of path to be excluded in new location
            $scope.folder = $scope.src_path.slice(0, $scope.src_path.slice(0, $scope.src_path.length-1).lastIndexOf('/')+1);
            var data = "csrf_token="+$('#csrf_token').val();
            $http({method: 'POST', url: url, data: data,
                headers: {'Content-Type': 'application/x-www-form-urlencoded'}}).
                success(function (oData) {
                    $scope.total = oData.results.length;
                    $scope.all_items = oData.results;
                    $scope.index = 0;
                    $('#copy-folder-modal').foundation('reveal', 'open');
                    $scope.copyFolder();
                }).
                error(function (oData, status) {
                    Notify.failure(oData.message);
                });
        };
        $scope.copyFolder = function () {
            $scope.copyingAll = true;
            $scope.copyChunk();
        };
        $scope.copyChunk = function () {
            var start = $scope.index * $scope.chunkSize;
            var end = start + $scope.chunkSize;
            if (end > $scope.total) {
                end = $scope.total;
            }
            var chunk = $scope.all_items.slice(start, end);
            var escapedChunk = chunk.map(function (key_name) {
                return encodeURIComponent(key_name);
            });
            var url = $scope.putKeysUrl.replace('_name_', $scope.bucketName).replace('_subpath_', $scope.prefix);
            var data = "csrf_token=" + $('#csrf_token').val() +
                       "&src_bucket=" + $scope.src_bucket +
                       "&folder_loc=" + $scope.folder +
                       "&keys=" + escapedChunk.join(',');
            $http({method: 'POST', url: url, data: data,
                headers: {'Content-Type': 'application/x-www-form-urlencoded'}}).
                success(function (oData) {
                    if (oData.errors !== undefined) {
                        console.log('error copying some keys ' + oData.errors);
                    }
                    $scope.progress = $scope.progress + $scope.chunkSize;
                    if ($scope.progress > $scope.total) {
                        $scope.progress = $scope.total;
                    }
                    if ($scope.copyingAll === true) {
                        var chunks = $scope.total / $scope.chunkSize;
                        $scope.index = $scope.index + 1;
                        if ($scope.index >= chunks) {
                            $('#copy-folder-modal').foundation('reveal', 'close');
                            $scope.copyingAll = false;
                            $scope.folder = '';
                            $scope.$broadcast('refresh');
                        }
                        else {
                            $scope.copyChunk();
                        }
                    }
                }).
                error(function (oData, status) {
                    $('#copy-folder-modal').foundation('reveal', 'close');
                    $scope.copyingAll = false;
                    Notify.failure("error copying some keys");
                });
        };
        $scope.cancelCopying = function () {
            $('#copy-folder-modal').foundation('reveal', 'close');
            $scope.copyingAll = false;
            $scope.$broadcast('refresh');
        };
        $scope.openSharedBucket = function($event) {
            var form = $('#open-shared-form');
            form.trigger('validate');
            invalidFields = form.find('[data-invalid]');
            if (invalidFields.length || $scope.isNotValid === true) {
                invalidFields.focus();
                $event.preventDefault();
                return;
            }
            var url = window.location.href;
            var bucket_name = $('#shared-bucket-name').val();
            var save_name = $('#save-bucket-to-list').is(':checked');
            if (Modernizr.localstorage && save_name === true) {
                var saved_names = localStorage.getItem($scope.storageKey);
                var names = (saved_names === null) ? [] : saved_names.split(',');
                if (names.indexOf(bucket_name) === -1) {
                    if (saved_names) {
                        saved_names = saved_names + "," + bucket_name;
                    }
                    else {
                        saved_names = bucket_name;
                    }
                }
                localStorage.setItem($scope.storageKey, saved_names);
            }
            window.location = $scope.contentsUrl.replace("_name_", bucket_name);
        };
        $scope.s3url_timer = undefined;
        $('#shared-object-path').on('keydown', function() {
            if ($scope.s3url_timer) {
                window.clearTimeout($scope.s3url_timer);
            }
            $scope.s3url_timer = window.setTimeout(function() {
                $scope.s3url_timer = undefined;
                $timeout(function() {
                    $scope.getSharedObjectUrl();
                });
            }, 2000);
        });
        $scope.getSharedObjectUrl = function() {
            var form = $('#download-object-form');
            form.trigger('validate');
            invalidFields = form.find('[data-invalid]');
            if (invalidFields.length || $scope.isNotValid === true) {
                invalidFields.focus();
                return;
            }
            var objectPath = $('#shared-object-path').val();
            var bucketName = objectPath.substring(0, objectPath.indexOf('/'));
            var key = objectPath.substring(objectPath.indexOf('/')+1);
            var url = $scope.itemUrl.replace('_name_', bucketName).replace('_subpath_', key);
            $scope.fetchingUrl = true;
            $http({method: 'POST', url: url, data: '',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'}}).
                success(function (oData) {
                    $scope.fetchingUrl = false;
                    if (oData.errors !== undefined) {
                        console.log('error getting shared object url ' + oData.errors);
                    }
                    $scope.sharedObjectUrl = oData.item_link;
                }).
                error(function (oData, status) {
                    $('#copy-folder-modal').foundation('reveal', 'close');
                    $scope.copyingAll = false;
                    Notify.failure("error getting shared object url");
                });
        };
        $scope.closeDialog = function() {
            $('#download-object-modal').foundation('reveal', 'close');
        };
        $scope.removeShared = function(item) {
            if (Modernizr.localstorage) {
                var saved_names = localStorage.getItem($scope.storageKey);
                var names = saved_names.split(',');
                names.splice(names.indexOf(item.bucket_name), 1);
                saved_names = names.join(',');
                localStorage.setItem($scope.storageKey, saved_names);
                $scope.$broadcast('refresh');
            }
        };
    })
;

