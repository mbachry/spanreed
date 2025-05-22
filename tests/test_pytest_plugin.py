pytest_plugins = ['pytester']


def test_plugin(testdir, settings):
    testdir.makeconftest(
        """
        import pytest

        from spanreed.models import message_from_data
        from tests.factories import MessageFactory

        @pytest.fixture(name='message_data')
        def _message_data():
            return MessageFactory.build(metadata__type='tests.models.UserCreated')


        @pytest.fixture()
        def message(message_data):
            return message_from_data(message_data)

        @pytest.fixture(name='other_message_data')
        def _other_message_data():
            return MessageFactory.build(metadata__type='tests.models.UserCreated')
    """
    )

    # create a temporary pytest test file
    testdir.makepyfile(
        """
        def test_mock_spanreed_publish_no_publish(mock_spanreed_publish):
            mock_spanreed_publish.assert_message_not_published('tests.models.UserCreated')


        def test_mock_spanreed_publish_publish_check(mock_spanreed_publish, message):
            message.data.publish()
            mock_spanreed_publish.assert_message_not_published('tests.models.BookingCreated')


        def test_mock_spanreed_publish_publish_check_same_type(mock_spanreed_publish, message, other_message_data):
            message.data.publish()
            mock_spanreed_publish.assert_message_not_published(message.metadata.type, data=other_message_data)
            mock_spanreed_publish.assert_message_published(message.metadata.type, data=message.data)


        def test_mock_spanreed_publish_published(mock_spanreed_publish, message):
            message.data.publish()
            mock_spanreed_publish.assert_message_published(message.metadata.type, data=message.data)


        def test_mock_spanreed_publish_published_without_checking_data(mock_spanreed_publish, message):
            message.data.publish()
            mock_spanreed_publish.assert_message_published(message.metadata.type)
    """
    )

    # run all tests with pytest
    result = testdir.runpytest()

    # check that all 3 tests passed
    result.assert_outcomes(passed=5)
